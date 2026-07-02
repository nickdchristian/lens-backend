# pyright: reportUnusedParameter=false, reportUntypedFunctionDecorator=false, reportUnknownMemberType=false, reportAny=false
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi_cache.decorator import cache

from src.api.dependencies import verify_ingestion_auth
from src.core.config import settings
from src.core.database import get_event_repository
from src.core.limiter import limiter
from src.models import ActionEvent
from src.repositories.protocol import EventRepositoryProtocol
from src.schemas import (
    ActionDataPayload,
    ActionResponse,
    EventListResponse,
    StatusResponse,
)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


def get_events_limit() -> str:
    """Return the rate limit for fetching events."""
    return settings.rate_limit_events


def get_api_limit() -> str:
    """Return the general API rate limit."""
    return settings.rate_limit_api


@router.post(
    "",
    response_model=StatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_ingestion_auth)],
)
@limiter.limit(get_events_limit)
async def create_event(
    request: Request,
    payload: ActionDataPayload,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
    background_tasks: BackgroundTasks,
):
    """Ingest a new CI/CD action event asynchronously."""
    event = ActionEvent(**payload.model_dump(exclude_unset=True))
    background_tasks.add_task(repo.create_event, event)
    return StatusResponse(status="success", message="Event accepted for processing")


@router.get("", response_model=EventListResponse)
@limiter.limit(get_api_limit)
@cache(expire=300)
async def get_all_events(
    request: Request,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=5000)] = 25,
    search: Annotated[str | None, Query()] = None,
    group_key: Annotated[str | None, Query()] = None,
    group_val: Annotated[str | None, Query()] = None,
):
    """Retrieve a list of all action events."""
    events = await repo.get_all_events(skip=skip, limit=limit, search=search, group_key=group_key, group_val=group_val)
    response_events = [ActionResponse.model_validate(e) for e in events]
    return EventListResponse(status="success", events=response_events)


@router.get("/artifact/{event_id}", response_model=ActionResponse)
@limiter.limit(get_api_limit)
@cache(expire=300)
async def get_event_by_id(
    request: Request,
    event_id: str,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
):
    """Retrieve a specific action event by its ID."""
    from fastapi import HTTPException
    event = await repo.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ActionResponse.model_validate(event)


@router.get("/repositories", response_model=list[str])
@limiter.limit(get_api_limit)
@cache(expire=300)
async def get_unique_repositories(
    request: Request,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
):
    """Get a list of all unique repositories."""
    return await repo.get_unique_repositories()


@router.get("/metrics", response_model=list[str])
@limiter.limit(get_api_limit)
@cache(expire=300)
async def get_available_metrics(
    request: Request,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
    repository: Annotated[str | None, Query()] = None,
):
    """Get a list of all available numeric metrics, optionally filtered by repository."""
    return await repo.get_available_metrics(repository)


@router.get("/{repository}", response_model=EventListResponse)
@limiter.limit(get_api_limit)
@cache(expire=300)
async def get_events_by_repo(
    request: Request,
    repository: str,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=5000)] = 25,
    search: Annotated[str | None, Query()] = None,
):
    """Retrieve a list of action events for a specific repository."""
    events = await repo.get_events_by_repository(repository, skip=skip, limit=limit, search=search)
    response_events = [ActionResponse.model_validate(e) for e in events]
    return EventListResponse(status="success", events=response_events)

@router.get("/{repository}/metrics/aggregated")
@limiter.limit(get_api_limit)
@cache(expire=300)
async def get_aggregated_metrics(
    request: Request,
    repository: str,
    metric_key: str,
    time_period: str,
    is_sum: bool,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
):
    """Retrieve aggregated metrics for a specific repository."""
    data = await repo.get_aggregated_metrics(repository, metric_key, time_period, is_sum)
    return {"status": "success", "data": data}
