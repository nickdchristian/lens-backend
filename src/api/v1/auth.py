# pyright: reportUnknownMemberType=false, reportAny=false
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer, SignatureExpired
import logging

logger = logging.getLogger(__name__)

from src.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

oauth = OAuth()
if settings.oauth_client_id and settings.oauth_client_secret:
    oauth.register(
        name="sso",
        client_id=settings.oauth_client_id,
        client_secret=settings.oauth_client_secret,
        authorize_url=settings.oauth_authorize_url,
        access_token_url=settings.oauth_token_url,
        userinfo_endpoint=settings.oauth_userinfo_url,
        client_kwargs={"scope": "read:user user:email"},
    )


def get_serializer() -> URLSafeTimedSerializer:
    secret = settings.session_secret_key
    return URLSafeTimedSerializer(secret, salt="lens-auth")


@router.get("/login")
async def login(request: Request):
    """Redirect to the OAuth provider for authentication."""
    if not settings.oauth_client_id:
        raise HTTPException(status_code=501, detail="OAuth is not configured")

    base_url = str(request.base_url)
    if "localhost" not in base_url and "127.0.0.1" not in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)
        
    redirect_uri = base_url + "api/v1/auth/callback"
    return await oauth.sso.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request, response: Response):
    """Handle the OAuth callback and set the session cookie."""
    if not settings.oauth_client_id:
        raise HTTPException(status_code=501, detail="OAuth is not configured")

    try:
        token = await oauth.sso.authorize_access_token(request)
    except Exception as e:
        logger.warning(f"OAuth authorization failed: {e}")
        return RedirectResponse(url="/?error=oauth_failed")

    user_info = None
    if settings.oauth_userinfo_url:
        resp = await oauth.sso.get(settings.oauth_userinfo_url, token=token)
        user_info = resp.json()
    else:
        user_info = token.get("userinfo")

    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user information")

    user_id = (
        user_info.get("login")
        or user_info.get("email")
        or user_info.get("id")
        or "unknown"
    )

    serializer = get_serializer()
    session_data = {"user": user_id, "name": user_info.get("name", user_id)}
    signed_session = serializer.dumps(session_data)

    frontend_url = "/"

    redirect = RedirectResponse(url=frontend_url)
    redirect.set_cookie(
        key="lens_session",
        value=signed_session,
        httponly=True,
        secure=not (
            "localhost" in str(request.base_url) or "127.0.0.1" in str(request.base_url)
        ),
        samesite="lax",
        max_age=86400 * 7,  # 1 week
    )
    return redirect


@router.post("/logout")
async def logout(request: Request):
    """Clear the session cookie."""
    response = Response(
        status_code=200, content='{"status": "ok"}', media_type="application/json"
    )
    is_localhost = "localhost" in str(request.base_url) or "127.0.0.1" in str(request.base_url)
    response.delete_cookie(
        key="lens_session", 
        httponly=True, 
        secure=not is_localhost,
        samesite="lax"
    )
    return response


@router.get("/me")
async def get_me(request: Request):
    """Return the current user's profile."""
    if not settings.oauth_client_id:
        return {"user": "admin", "name": "Admin (Auth Disabled)"}

    cookie = request.cookies.get("lens_session")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")

    serializer = get_serializer()
    try:
        session_data = serializer.loads(cookie, max_age=86400 * 7)
        return session_data
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired") from None
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session") from None
