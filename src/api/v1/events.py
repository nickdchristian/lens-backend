# pyright: reportUnusedParameter=false, reportUntypedFunctionDecorator=false, reportUnknownMemberType=false, reportAny=false
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi_cache.decorator import cache

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
    return settings.rate_limit_events


def get_api_limit() -> str:
    return settings.rate_limit_api


@router.post("", response_model=StatusResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(get_events_limit)
async def create_event(
    request: Request,
    payload: ActionDataPayload,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
    background_tasks: BackgroundTasks,
):
    event = ActionEvent(**payload.model_dump())
    background_tasks.add_task(repo.create_event, event)
    return StatusResponse(status="success", message="Event accepted for processing")


@router.get("/{repository}", response_model=EventListResponse)
@limiter.limit(get_api_limit)
@cache(expire=5)
async def get_events_by_repo(
    request: Request,
    repository: str,
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    events = await repo.get_events_by_repository(repository, limit=limit)
    response_events = [ActionResponse.model_validate(e) for e in events]
    return EventListResponse(status="success", events=response_events)
