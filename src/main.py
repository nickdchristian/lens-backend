# pyright: reportUnusedParameter=false, reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnusedCallResult=false
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.v1.events import router as events_router
from src.core.config import settings
from src.core.database import get_event_repository, setup_db
from src.core.limiter import limiter
from src.core.logging import setup_logging
from src.repositories.protocol import EventRepositoryProtocol

logger = logging.getLogger("src.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the application lifecycle, including logging and database setup."""
    setup_logging()
    logger.info("Starting up Lens Backend")
    
    if settings.redis_url:
        redis = aioredis.from_url(settings.redis_url)
        FastAPICache.init(RedisBackend(redis))
    else:
        FastAPICache.init(InMemoryBackend())

    if settings.database_type == "mongodb":
        if not settings.mongo_uri or not settings.mongo_db_name:
            raise ValueError("mongo_uri and mongo_db_name must be set for mongodb")
        from motor.motor_asyncio import AsyncIOMotorClient

        app.state.mongo_client = AsyncIOMotorClient(settings.mongo_uri)
    elif settings.database_type == "dynamodb":
        if not settings.aws_region or not settings.dynamo_table_name:
            raise ValueError(
                "aws_region and dynamo_table_name must be set for dynamodb"
            )
        import aioboto3

        app.state.dynamo_session = aioboto3.Session(region_name=settings.aws_region)
    elif settings.database_type == "mock":
        pass  # Skip database initialization for tests
    else:
        raise ValueError(f"Unsupported database type: {settings.database_type}")

    await setup_db(app)

    yield

    if settings.database_type == "mongodb":
        app.state.mongo_client.close()
        
    logger.info("Shutting down Lens Backend")


__title__ = "Lens API"
__description__ = "Event ingestion backend for the Lens application"
__version__ = "0.3.0"

app = FastAPI(
    title=__title__,
    description=__description__,
    version=__version__,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]

@app.middleware("http")
async def timing_middleware(request: Request, call_next): # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
    """Intercept requests to calculate and log execution time."""
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {process_time * 1000:.2f}ms"
    )
    return response

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(events_router)


@app.get("/health")
async def health_check(
    repo: Annotated[EventRepositoryProtocol, Depends(get_event_repository)],
):
    """Verify application and database health."""
    is_db_alive = await repo.ping()
    if not is_db_alive:
        logger.error("Health check failed: Database is unreachable")
        raise HTTPException(
            status_code=503, 
            detail={"status": "error", "checks": {"database": "unreachable"}}
        )
        
    return {"status": "ok"}
