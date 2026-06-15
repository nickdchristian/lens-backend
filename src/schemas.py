# pyright: reportExplicitAny=false, reportUnannotatedClassAttribute=false
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    status: str
    message: str


class ActionDataPayload(BaseModel):
    repository: str
    commit_sha: str
    workflow_name: str
    artifact_version: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    custom_data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)


class ActionResponse(BaseModel):
    id: str
    repository: str
    commit_sha: str
    workflow_name: str
    artifact_version: str | None = None
    tags: dict[str, str]
    custom_data: dict[str, Any]
    metrics: dict[str, float]
    timestamp: datetime

    model_config = {
        "from_attributes": True,
    }


class EventListResponse(BaseModel):
    status: str
    events: list[ActionResponse]
