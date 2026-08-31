from fastapi import Depends, HTTPException, Request, status
from clerk_backend_api import authenticate_request, AuthenticateRequestOptions

from .config import settings
from .database import get_or_create_clerk_user, get_user_by_clerk_id


def get_current_user(request: Request):
    """Verify the Clerk session token and return the local FinMan user."""
    if not settings.clerk_secret_key:
        raise HTTPException(
            status_code=500,
            detail="Clerk authentication is not configured on the server.",
        )

    try:
        auth_state = authenticate_request(
            request,
            AuthenticateRequestOptions(
                secret_key=settings.clerk_secret_key,
                jwt_key=settings.clerk_jwt_key or None,
                authorized_parties=[settings.frontend_origin],
                accepts_token=["session_token"],
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Clerk session.",
        ) from exc

    if not auth_state.is_signed_in:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in.",
        )

    clerk_user_id = auth_state.payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk session does not contain a user ID.",
        )

    return get_or_create_clerk_user(clerk_user_id)