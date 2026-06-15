# pyright: reportUnusedParameter=false, reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnusedCallResult=false
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.v1.events import router as events_router
from src.core.config import settings
from src.core.database import setup_db
from src.core.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize connection pools
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

    # Startup logic for indexes/tables
    await setup_db(app)

    yield

    # Shutdown connection pools safely
    if settings.database_type == "mongodb":
        app.state.mongo_client.close()


__title__ = "Lens API"
__description__ = "Event ingestion backend for the Lens application"
__version__ = "0.1.0"

app = FastAPI(
    title=__title__,
    description=__description__,
    version=__version__,
    lifespan=lifespan,
)

# Setup Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]

# CORS
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routers
app.include_router(events_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
