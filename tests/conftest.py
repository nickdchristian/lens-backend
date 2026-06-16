# pyright: reportUnusedParameter=false
from collections.abc import AsyncGenerator, Generator
from typing import override

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

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
    async def get_events_by_repository(
        self, repository: str, limit: int = 100
    ) -> list[ActionEvent]:
        self.get_events_call_count += 1
        filtered = [e for e in self.events if e.repository == repository]
        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered[:limit]

    @override
    async def ping(self) -> bool:
        return True


mock_repo_instance = MockEventRepository()


async def override_get_event_repository(
    request: Request,
) -> AsyncGenerator[EventRepositoryProtocol, None]:
    """Dependency override that yields the MockEventRepository."""
    yield mock_repo_instance


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Return a TestClient configured with mock dependencies."""
    app.dependency_overrides[get_event_repository] = override_get_event_repository
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_repo() -> Generator[MockEventRepository, None, None]:
    """Return the MockEventRepository instance after clearing its state."""
    mock_repo_instance.events.clear()
    mock_repo_instance.get_events_call_count = 0
    yield mock_repo_instance
