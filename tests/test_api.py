# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import pytest
from fastapi.testclient import TestClient

from src.models import ActionEvent
from tests.conftest import MockEventRepository


@pytest.mark.asyncio
async def test_create_event_success(client: TestClient, mock_repo: MockEventRepository):
    """Test successful creation of an event."""
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

    assert response.status_code == 202
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
    """Test event creation with invalid payload."""
    payload = {
        "repository": "lens",
        "workflow_name": "ci-build",
    }

    response = client.post("/api/v1/events", json=payload)

    assert response.status_code == 422
    assert len(mock_repo.events) == 0


@pytest.mark.asyncio
async def test_get_events_success(client: TestClient, mock_repo: MockEventRepository):
    """Test fetching events for a specific repository."""
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

    for e in data["events"]:
        assert e["repository"] == "lens"


@pytest.mark.asyncio
async def test_get_events_pagination(
    client: TestClient, mock_repo: MockEventRepository
):
    """Test pagination for fetched events."""
    for i in range(15):
        mock_repo.events.append(
            ActionEvent(
                id=f"id_{i}",
                repository="lens",
                commit_sha=f"sha{i}",
                workflow_name="build",
            )
        )

    response = client.get("/api/v1/events/lens?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 5


@pytest.mark.asyncio
async def test_health_check(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_rate_limiting(client: TestClient):
    """Test API rate limiting."""
    payload = {
        "repository": "lens",
        "commit_sha": "limit-test",
        "workflow_name": "ci-build",
    }

    for _ in range(101):
        response = client.post("/api/v1/events", json=payload)
        if response.status_code == 429:
            assert "Rate limit exceeded" in response.text
            return

    raise AssertionError("Rate limit was not triggered after 100 requests")


@pytest.mark.asyncio
async def test_caching(client: TestClient, mock_repo: MockEventRepository):
    """Test response caching."""
    # Initial request
    resp1 = client.get("/api/v1/events/cache-test-repo")
    assert resp1.status_code == 200

    # 9 subsequent identical requests
    for _ in range(9):
        resp = client.get("/api/v1/events/cache-test-repo")
        assert resp.status_code == 200

    # The database repository should have only been hit exactly ONCE
    # The other 9 were served directly from the FastAPICache InMemoryBackend
    assert mock_repo.get_events_call_count == 1


@pytest.mark.asyncio
async def test_authentication(client: TestClient):
    """Test that the API key authentication works."""
    from src.api.dependencies import verify_ingestion_auth
    from src.core.config import settings
    from src.core.limiter import limiter
    from src.main import app

    limiter._storage.storage.clear()

    app.dependency_overrides.pop(verify_ingestion_auth, None)

    original_api_key = settings.api_key
    settings.api_key = "secret_test_key"

    try:
        payload = {
            "repository": "lens",
            "commit_sha": "auth-test",
            "workflow_name": "ci-build",
        }

        resp_no_auth = client.post("/api/v1/events", json=payload)
        assert resp_no_auth.status_code == 401

        resp_wrong_auth = client.post(
            "/api/v1/events", json=payload, headers={"X-API-Key": "wrong"}
        )
        assert resp_wrong_auth.status_code == 401

        resp_correct_auth = client.post(
            "/api/v1/events", json=payload, headers={"X-API-Key": "secret_test_key"}
        )
        assert resp_correct_auth.status_code == 202

        resp_bearer = client.post(
            "/api/v1/events",
            json=payload,
            headers={"Authorization": "Bearer secret_test_key"},
        )
        assert resp_bearer.status_code == 202

    finally:
        settings.api_key = original_api_key
        from tests.conftest import override_verify_ingestion_auth

        app.dependency_overrides[verify_ingestion_auth] = override_verify_ingestion_auth
