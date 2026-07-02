# pyright: reportUnusedParameter=false
from collections.abc import AsyncGenerator, Generator
from typing import override

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from src.api.dependencies import verify_ingestion_auth
from src.core.database import get_event_repository
from src.main import app
from src.models import ActionEvent
from src.repositories.protocol import EventRepositoryProtocol


class MockEventRepository(EventRepositoryProtocol):
    def __init__(self) -> None:
        """Initialize an empty mock repository."""
        self.events: list[ActionEvent] = []
        self.get_events_call_count: int = 0

    @override
    async def setup(self) -> None:
        pass

    @override
    async def create_event(self, event: ActionEvent) -> ActionEvent:
        import uuid

        if not event.id:
            event.id = str(uuid.uuid4())
        self.events.append(event)
        return event

    @override
    async def get_aggregated_metrics(
        self, repository: str, metric_key: str, time_period: str, is_sum: bool
    ) -> list[dict[str, float | int]]:
        return []

    @override
    async def get_unique_repositories(self) -> list[str]:
        repos = {e.repository for e in self.events if e.repository}
        return list(repos)

    @override
    async def get_available_metrics(self, repository: str | None = None) -> list[str]:
        metrics: set[str] = set()
        for e in self.events:
            if repository and e.repository != repository:
                continue
            if e.metrics:
                for k in e.metrics.keys():
                    metrics.add(k)
        return list(metrics)

    @override
    async def get_events_by_repository(
        self, repository: str, skip: int = 0, limit: int = 25, search: str | None = None
    ) -> list[ActionEvent]:
        self.get_events_call_count += 1
        events = [e for e in self.events if e.repository == repository]
        if search:
            events = [
                e
                for e in events
                if search.lower() in (e.workflow_name or "").lower()
                or search.lower() in (e.commit_sha or "").lower()
            ]
        events.sort(key=lambda x: x.timestamp or "", reverse=True)
        if skip > 0:
            events = events[skip:]
        return events[:limit]

    @override
    async def get_all_events(
        self,
        skip: int = 0,
        limit: int = 25,
        search: str | None = None,
        group_key: str | None = None,
        group_val: str | None = None,
    ) -> list[ActionEvent]:
        events = list(self.events)
        if search:
            events = [
                e
                for e in events
                if search.lower() in (e.workflow_name or "").lower()
                or search.lower() in (e.commit_sha or "").lower()
                or search.lower() in (e.repository or "").lower()
            ]
        if group_key and group_val:
            filtered: list[ActionEvent] = []
            for e in events:
                if (
                    (e.tags and e.tags.get(group_key) == group_val)
                    or (e.custom_data and e.custom_data.get(group_key) == group_val)
                    or getattr(e, group_key, None) == group_val
                ):
                    filtered.append(e)
            events = filtered
        events.sort(key=lambda x: x.timestamp or "", reverse=True)
        if skip > 0:
            events = events[skip:]
        return events[:limit]

    @override
    async def get_event_by_id(self, event_id: str) -> ActionEvent | None:
        for e in self.events:
            if e.id == event_id:
                return e
        return None

    @override
    async def ping(self) -> bool:
        return True


mock_repo_instance = MockEventRepository()


async def override_get_event_repository(
    request: Request,
) -> AsyncGenerator[EventRepositoryProtocol, None]:
    """Dependency override that yields the MockEventRepository."""
    yield mock_repo_instance


async def override_verify_ingestion_auth() -> None:
    pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Return a TestClient configured with mock dependencies."""
    app.dependency_overrides[get_event_repository] = override_get_event_repository
    app.dependency_overrides[verify_ingestion_auth] = override_verify_ingestion_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_repo() -> Generator[MockEventRepository, None, None]:
    """Return the MockEventRepository instance after clearing its state."""
    mock_repo_instance.events.clear()
    mock_repo_instance.get_events_call_count = 0
    yield mock_repo_instance
