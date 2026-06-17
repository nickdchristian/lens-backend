# pyright: reportExplicitAny=false, reportUnannotatedClassAttribute=false
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    status: str
    message: str


class ActionDataPayload(BaseModel):
    repository: str = Field(min_length=1, max_length=100)
    commit_sha: str = Field(min_length=1, max_length=40)
    workflow_name: str = Field(min_length=1, max_length=100)
    artifact_version: str | None = Field(default=None, max_length=100)
    tags: dict[str, str] = Field(default_factory=dict)
    custom_data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)


class ActionResponse(BaseModel):
    id: str
    repository: str
    commit_sha: str
    workflow_name: str
    artifact_version: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    custom_data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime

    model_config = {
        "from_attributes": True,
    }


class EventListResponse(BaseModel):
    status: str
    events: list[ActionResponse]
