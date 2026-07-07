import logging
import secrets
import time
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from joserfc import jwt
from joserfc.jwk import KeySet

from src.core.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_token = HTTPBearer(auto_error=False)

_jwks_cache = None
_jwks_cache_time = 0


async def get_jwks() -> Any:
    global _jwks_cache, _jwks_cache_time
    if _jwks_cache and time.time() - _jwks_cache_time < 3600:
        return _jwks_cache

    issuer = settings.oidc_issuer_url
    if not issuer:
        return None

    try:
        async with httpx.AsyncClient() as client:
            jwks_url = f"{issuer.rstrip('/')}/.well-known/jwks.json"
            if "githubusercontent" in issuer:
                jwks_url = f"{issuer.rstrip('/')}/.well-known/jwks"

            resp = await client.get(
                f"{issuer.rstrip('/')}/.well-known/openid-configuration"
            )
            if resp.status_code == 200:
                jwks_url = resp.json().get("jwks_uri", jwks_url)

            jwks_resp = await client.get(jwks_url)
            jwks_resp.raise_for_status()

            _jwks_cache = KeySet.import_key_set(jwks_resp.json())
            _jwks_cache_time = time.time()
            return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to fetch JWKS from {issuer}: {e}")
        return None


async def verify_ingestion_auth(
    api_key: Annotated[str | None, Depends(api_key_header)],
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_token)],
) -> str | None:
    """
    Verify that the incoming request is authorized to ingest data.
    Returns the authorized repository name (if OIDC), or None if using a global API Key.
    """
    if bearer and bearer.credentials and settings.oidc_issuer_url:
        token = bearer.credentials
        try:
            jwks = await get_jwks()
            if not jwks:
                raise ValueError("Failed to load JWKS")

            claims_options = {
                "iss": {"essential": True, "value": settings.oidc_issuer_url}
            }
            if settings.oidc_audience:
                claims_options["aud"] = {
                    "essential": True,
                    "value": settings.oidc_audience,
                }

            registry = jwt.JWTClaimsRegistry(**claims_options)
            token_obj = jwt.decode(token, _jwks_cache)
            claims = token_obj.claims
            registry.validate(claims)

            repository = claims.get("repository") or claims.get("project_path")
            if not repository:
                raise ValueError(
                    "Token is missing 'repository' or 'project_path' claim"
                )

            repository_owner = claims.get("repository_owner") or claims.get(
                "namespace_path"
            )
            if not settings.oidc_allowed_owners:
                raise ValueError(
                    "OIDC multi-tenant ingestion is disabled (no allowed owners configured)"
                )
            if (
                not repository_owner
                or repository_owner not in settings.oidc_allowed_owners
            ):
                raise ValueError(
                    f"Repository owner '{repository_owner}' is not whitelisted"
                )

            return repository
        except Exception as e:
            logger.warning(f"OIDC validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid OIDC token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

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

    return None


def get_serializer() -> Any:
    secret = settings.session_secret_key
    return URLSafeTimedSerializer(secret, salt="lens-auth")


async def verify_user_session(request: Request) -> None:
    """Verify that the user has a valid dashboard session."""
    if not settings.oauth_client_id:
        return None  # Auth is disabled for the dashboard

    cookie = request.cookies.get("lens_session")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")

    serializer = get_serializer()

    try:
        serializer.loads(cookie, max_age=86400 * 7)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired") from None
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session") from None
