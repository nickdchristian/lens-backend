import pytest
from fastapi.testclient import TestClient

from src.models import ActionEvent
from tests.conftest import MockEventRepository


@pytest.mark.asyncio
async def test_create_event_success(client: TestClient, mock_repo: MockEventRepository):
    payload = {
        "repository": "lens",
        "commit_sha": "abc123def456",
        "workflow_name": "ci-build",
        "artifact_version": "v1.0.0",
        "tags": {"env": "prod"},
        "custom_data": {"tests_passed": True},
        "metrics": {"build_time": 42.5},
    }

    response = client.post("/api/v1/events", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"

    assert len(mock_repo.events) == 1
    event = mock_repo.events[0]
    assert event.repository == "lens"
    assert event.commit_sha == "abc123def456"


@pytest.mark.asyncio
async def test_create_event_validation_error(
    client: TestClient, mock_repo: MockEventRepository
):
    # Missing required field 'commit_sha'
    payload = {
        "repository": "lens",
        "workflow_name": "ci-build",
    }

    response = client.post("/api/v1/events", json=payload)

    assert response.status_code == 422
    assert len(mock_repo.events) == 0


@pytest.mark.asyncio
async def test_get_events_success(
    client: TestClient, mock_repo: MockEventRepository
):
    # Insert dummy data
    event1 = ActionEvent(
        id="1", repository="lens", commit_sha="sha1", workflow_name="build"
    )
    event2 = ActionEvent(
        id="2", repository="lens", commit_sha="sha2", workflow_name="deploy"
    )
    event3 = ActionEvent(
        id="3", repository="other-repo", commit_sha="sha3", workflow_name="build"
    )

    mock_repo.events.extend([event1, event2, event3])

    response = client.get("/api/v1/events/lens")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert len(data["events"]) == 2
    
    # Verify it only fetched the requested repository
    for e in data["events"]:
        assert e["repository"] == "lens"


@pytest.mark.asyncio
async def test_get_events_pagination(
    client: TestClient, mock_repo: MockEventRepository
):
    # Insert 15 events
    for i in range(15):
        mock_repo.events.append(
            ActionEvent(
                id=f"id_{i}",
                repository="lens",
                commit_sha=f"sha{i}",
                workflow_name="build"
            )
        )

    # Request only 5
    response = client.get("/api/v1/events/lens?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 5


@pytest.mark.asyncio
async def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_rate_limiting(client: TestClient):
    payload = {
        "repository": "lens",
        "commit_sha": "limit-test",
        "workflow_name": "ci-build",
    }
    
    # The default limit is 100/minute. 
    # Hitting it 101 times sequentially will trigger the rate limiter.
    for _ in range(101):
        response = client.post("/api/v1/events", json=payload)
        if response.status_code == 429:
            assert "Rate limit exceeded" in response.text
            return
            
    raise AssertionError("Rate limit was not triggered after 100 requests")
