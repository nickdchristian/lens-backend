# pyright: reportExplicitAny=false
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


from src.schemas import ArtifactData


class ActionEvent(BaseModel):
    id: str | None = None
    workflow_name: str
    repository: str | None = None
    commit_sha: str | None = None
    artifact: ArtifactData | None = None

    tags: dict[str, str] = Field(default_factory=dict)
    custom_data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
