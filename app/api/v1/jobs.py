"""
API v1 – Job endpoints
"""
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.job import (
    JobCancelResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
    StatsResponse,
)
from app.services.job_service import (
    cancel_job,
    create_job,
    get_job,
    get_stats,
    list_jobs,
    process_job,
)

router = APIRouter(prefix="/jobs")


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new job",
    description=(
        "Creates a new background job and immediately queues it for async processing. "
        "The job starts in **pending** state and transitions through "
        "**in_progress → completed | failed**."
    ),
)
async def submit_job(
    body: JobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    job = await create_job(db, body)
    background_tasks.add_task(process_job, job.id)
    return JobResponse.model_validate(job)


@router.get(
    "/",
    response_model=JobListResponse,
    summary="List all jobs",
    description="Returns a paginated list of jobs, optionally filtered by status.",
)
async def list_all_jobs(
    status: str | None = Query(
        default=None,
        description="Filter by job status",
        examples=["pending", "in_progress", "completed", "failed", "cancelled"],
    ),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    return await list_jobs(db, status=status, skip=skip, limit=limit)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Job statistics",
    description="Returns aggregate counts broken down by status.",
)
async def job_statistics(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    return await get_stats(db)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job details",
    description="Fetch the full details and current status of a specific job by its ID.",
)
async def get_job_by_id(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    job = await get_job(db, job_id)
    return JobResponse.model_validate(job)


@router.delete(
    "/{job_id}/cancel",
    response_model=JobCancelResponse,
    summary="Cancel a job",
    description=(
        "Cancels a **pending** or **in_progress** job. "
        "Returns 409 if the job has already reached a terminal state."
    ),
)
async def cancel_job_by_id(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobCancelResponse:
    job = await cancel_job(db, job_id)
    return JobCancelResponse(id=job.id, message=f"Job '{job_id}' has been cancelled.")
