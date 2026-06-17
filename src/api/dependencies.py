import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_token = HTTPBearer(auto_error=False)


async def verify_ingestion_auth(
    api_key: Annotated[str | None, Depends(api_key_header)],
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_token)],
) -> None:
    """
    Verify that the incoming request is authorized to ingest data.

    Currently supports a static API key via X-API-Key or Bearer token.
    Future OIDC implementation will verify the JWT signature here if a Bearer
    token is provided.
    """
    provided_token = api_key or (bearer.credentials if bearer else None)

    if not provided_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not settings.api_key or not secrets.compare_digest(
        provided_token, settings.api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
