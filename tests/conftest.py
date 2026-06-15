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
        self.events: list[ActionEvent] = []

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
        # Filter, sort descending by timestamp, and limit
        filtered = [e for e in self.events if e.repository == repository]
        sorted_events = sorted(filtered, key=lambda x: x.timestamp, reverse=True)
        return sorted_events[:limit]


mock_repo_instance = MockEventRepository()


async def override_get_event_repository(
    request: Request,
) -> AsyncGenerator[EventRepositoryProtocol, None]:
    yield mock_repo_instance


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_event_repository] = override_get_event_repository
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_repo() -> MockEventRepository:
    # Clear events before each test run
    mock_repo_instance.events.clear()
    return mock_repo_instance
