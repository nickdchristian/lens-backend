# pyright: reportExplicitAny=false
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ActionEvent(BaseModel):
    id: str | None = None
    repository: str
    commit_sha: str
    workflow_name: str
    artifact_version: str | None = None

    tags: dict[str, str] = Field(default_factory=dict)
    custom_data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
