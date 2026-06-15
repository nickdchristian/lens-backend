# pyright: reportUnusedParameter=false
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.routes import router as events_router
from src.config import settings
from src.database import init_db
from src.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB indexes or perform connections
    await init_db()
    yield
    # Shutdown logic if necessary


app = FastAPI(
    title="Lens API",
    description="Event ingestion backend for the Lens application",
    version="0.1.0",
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
