# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
from collections.abc import AsyncGenerator

import aioboto3  # pyright: ignore[reportMissingTypeStubs]
from motor.motor_asyncio import AsyncIOMotorClient

from src.config import settings
from src.repositories.dynamo import DynamoDBRepository
from src.repositories.mongo import MongoRepository
from src.repositories.protocol import EventRepositoryProtocol

# Global clients
_dynamo_session = None
_mongo_client = None


async def init_db() -> None:
    """Initialize database constraints/indexes."""
    # We grab the repository temporarily just to run setup()
    async for repo in get_event_repository():
        await repo.setup()
        break


async def get_event_repository() -> AsyncGenerator[EventRepositoryProtocol, None]:
    """FastAPI Dependency for getting the configured EventRepository."""
    global _dynamo_session, _mongo_client

    if settings.database_type == "dynamodb":
        if not settings.aws_region or not settings.dynamo_table_name:
            raise ValueError(
                "aws_region and dynamo_table_name must be set for dynamodb"
            )

        if _dynamo_session is None:
            _dynamo_session = aioboto3.Session(region_name=settings.aws_region)

        async with _dynamo_session.resource("dynamodb") as dynamo_resource:
            table = await dynamo_resource.Table(settings.dynamo_table_name)
            yield DynamoDBRepository(table)

    elif settings.database_type == "mongodb":
        if not settings.mongo_uri or not settings.mongo_db_name:
            raise ValueError("mongo_uri and mongo_db_name must be set for mongodb")

        if _mongo_client is None:
            _mongo_client = AsyncIOMotorClient(settings.mongo_uri)

        db = _mongo_client[settings.mongo_db_name]
        collection = db["events"]
        yield MongoRepository(collection)

    else:
        raise ValueError(f"Unsupported database type: {settings.database_type}")
