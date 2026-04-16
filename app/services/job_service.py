"""
Job service – all database interactions and async processing logic lives here.
"""
import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import JobAlreadyCancelledError, JobNotFoundError
from app.db.database import AsyncSessionLocal
from app.models.job import Job
from app.schemas.job import JobCreate, JobListResponse, JobResponse, StatsResponse

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


# ──────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────

async def create_job(db: AsyncSession, payload: JobCreate) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        name=payload.name,
        payload=payload.payload,
        priority=payload.priority,
        status="pending",
        created_at=_utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    logger.info("Job created: %s (name=%s)", job.id, job.name)
    return job


async def get_job(db: AsyncSession, job_id: str) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(job_id)
    return job


async def list_jobs(
    db: AsyncSession,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> JobListResponse:
    query = select(Job).order_by(Job.priority.desc(), Job.created_at.asc())
    count_query = select(func.count()).select_from(Job)

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(query.offset(skip).limit(limit))
    jobs = result.scalars().all()

    return JobListResponse(total=total, items=list(jobs))  # type: ignore[arg-type]


async def cancel_job(db: AsyncSession, job_id: str) -> Job:
    job = await get_job(db, job_id)
    if job.status in TERMINAL_STATUSES:
        raise JobAlreadyCancelledError(job_id)
    job.status = "cancelled"
    job.completed_at = _utcnow()
    await db.commit()
    await db.refresh(job)
    logger.info("Job cancelled: %s", job_id)
    return job


async def get_stats(db: AsyncSession) -> StatsResponse:
    result = await db.execute(
        select(Job.status, func.count(Job.id))
        .group_by(Job.status)
    )
    rows = result.all()
    counts: dict[str, int] = {row[0]: row[1] for row in rows}
    total = sum(counts.values())
    return StatsResponse(
        total=total,
        pending=counts.get("pending", 0),
        in_progress=counts.get("in_progress", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        cancelled=counts.get("cancelled", 0),
    )


# ──────────────────────────────────────────────
# Async background worker
# ──────────────────────────────────────────────

async def _simulate_work(job: Job) -> str:
    """Simulates actual job work with a random delay."""
    delay = random.randint(settings.JOB_MIN_DELAY, settings.JOB_MAX_DELAY)
    logger.info("Job %s starting – simulated work for %ds", job.id, delay)
    await asyncio.sleep(delay)

    # Simulate random failure
    if random.random() < settings.JOB_FAILURE_RATE:
        raise RuntimeError("Simulated random processing failure.")

    # Build a meaningful result based on job name
    return (
        f"Job '{job.name}' completed successfully. "
        f"Processed payload keys: {list((job.payload or {}).keys()) or 'none'}."
    )


async def process_job(job_id: str) -> None:
    """
    Run inside asyncio background task.
    Opens its own DB session so it is independent of the request session.
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if job is None:
                logger.error("Background worker: job %s not found.", job_id)
                return

            if job.status == "cancelled":
                logger.info("Job %s was cancelled before processing started.", job_id)
                return

            # Mark in_progress
            job.status = "in_progress"
            job.started_at = _utcnow()
            await db.commit()

            # Do the work
            output = await _simulate_work(job)

            # Re-fetch to guard against concurrent cancellation
            await db.refresh(job)
            if job.status == "cancelled":
                logger.info("Job %s was cancelled mid-flight.", job_id)
                return

            job.status = "completed"
            job.result = output
            job.completed_at = _utcnow()
            await db.commit()
            logger.info("Job %s completed.", job_id)

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Job %s failed: %s", job_id, exc)
            try:
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if job and job.status not in TERMINAL_STATUSES:
                    job.status = "failed"
                    job.error = str(exc)
                    job.completed_at = _utcnow()
                    await db.commit()
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to update job %s error state.", job_id)
