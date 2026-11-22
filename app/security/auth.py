"""
API Authentication & Authorization Guards for Meco Control Centre (Phase 9).
"""
import logging

from fastapi import Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import get_settings

logger = logging.getLogger("meco.security.auth")
security_bearer = HTTPBearer(auto_error=False)


def verify_operator_access(
    auth_header: HTTPAuthorizationCredentials | None = Security(security_bearer),  # noqa: B008
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> bool:
    """
    Verifies that the incoming request to operator control endpoints contains
    valid authentication credentials when API_AUTH_TOKEN is configured.
    """
    settings = get_settings()
    configured_token = settings.api_auth_token

    # If no token is configured in environment, allow local loopback/dev access
    if not configured_token or not configured_token.strip():
        return True

    provided_token = None
    if auth_header and auth_header.credentials:
        provided_token = auth_header.credentials.strip()
    elif x_api_key and x_api_key.strip():
        provided_token = x_api_key.strip()

    if not provided_token or provided_token != configured_token.strip():
        logger.warning("UNAUTHORIZED ACCESS ATTEMPT on operator control endpoint.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing operator authorization credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
