from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────

class JobCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["send-email", "generate-report"],
        description="Human-readable job name / type identifier.",
    )
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary JSON payload passed to the job processor.",
        examples=[{"recipient": "user@example.com", "template": "welcome"}],
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Job priority (0 = normal, 10 = highest). Higher priority jobs run first.",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "name": "generate-report",
            "payload": {"report_type": "monthly", "year": 2025},
            "priority": 1,
        }
    }}


# ──────────────────────────────────────────────
# Response schemas
# ──────────────────────────────────────────────

JobStatus = Literal["pending", "in_progress", "completed", "failed", "cancelled"]


class JobResponse(BaseModel):
    id: str
    name: str
    payload: dict[str, Any] | None
    status: JobStatus
    result: str | None
    error: str | None
    priority: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobSummary(BaseModel):
    """Lightweight version used in list endpoints."""
    id: str
    name: str
    status: JobStatus
    priority: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    total: int
    items: list[JobSummary]


class JobCancelResponse(BaseModel):
    id: str
    message: str


class StatsResponse(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    failed: int
    cancelled: int
