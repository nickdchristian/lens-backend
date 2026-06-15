# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportAny=false
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request

from src.core.config import settings
from src.repositories.dynamo import DynamoDBRepository
from src.repositories.mongo import MongoRepository
from src.repositories.protocol import EventRepositoryProtocol


async def setup_db(app: FastAPI) -> None:
    """Initialize database constraints/indexes."""
    if settings.database_type == "dynamodb":
        async with app.state.dynamo_session.resource("dynamodb") as dynamo_resource:
            table = await dynamo_resource.Table(settings.dynamo_table_name)
            repo = DynamoDBRepository(table)
            await repo.setup()
    elif settings.database_type == "mongodb":
        client = app.state.mongo_client
        db = client[settings.mongo_db_name]
        repo = MongoRepository(db["events"])
        await repo.setup()


async def get_event_repository(
    request: Request,
) -> AsyncGenerator[EventRepositoryProtocol, None]:
    """FastAPI Dependency for getting the configured EventRepository."""
    if settings.database_type == "dynamodb":
        async with request.app.state.dynamo_session.resource(
            "dynamodb"
        ) as dynamo_resource:
            table = await dynamo_resource.Table(settings.dynamo_table_name)
            yield DynamoDBRepository(table)

    elif settings.database_type == "mongodb":
        client = request.app.state.mongo_client
        db = client[settings.mongo_db_name]
        collection = db["events"]
        yield MongoRepository(collection)
