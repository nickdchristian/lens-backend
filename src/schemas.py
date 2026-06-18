# pyright: reportExplicitAny=false, reportUnannotatedClassAttribute=false
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class StatusResponse(BaseModel):
    status: str
    message: str


class ArtifactData(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)


class ActionDataPayload(BaseModel):
    workflow_name: str = Field(min_length=1, max_length=100)
    repository: str | None = Field(default=None, min_length=1, max_length=100)
    commit_sha: str | None = Field(default=None, min_length=1, max_length=40)
    artifact: ArtifactData | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    custom_data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_context(self) -> "ActionDataPayload":
        if not self.repository and not self.artifact:
            raise ValueError(
                "Event must have either 'repository' or 'artifact' context"
            )
        return self


class ActionResponse(BaseModel):
    id: str
    workflow_name: str
    repository: str | None = None
    commit_sha: str | None = None
    artifact: ArtifactData | None = None
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
