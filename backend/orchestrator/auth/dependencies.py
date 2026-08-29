"""
FastAPI Security & RBAC Dependencies (Phase 4B).

Enforces:
  - Valid JWT Bearer Authentication header.
  - Role-Based Access Control (RBAC) per endpoint.
"""

from typing import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.orchestrator.auth.security import UserTokenData, decode_access_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UserTokenData:
    """
    Extract and validate the current authenticated user from Bearer Token.
    Raises 401 Unauthorized if missing, invalid, or expired.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_access_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


async def get_current_user_or_demo(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UserTokenData:
    """
    Optional helper: fallback to demo officer if no credentials provided (for dev convenience).
    """
    if credentials is None or not credentials.credentials:
        return UserTokenData(
            user_id="00000000-0000-0000-0000-000000000001",
            email="officer@borderguard.gov",
            role="officer",
            badge_number="BG-7492",
            checkpoint_id="CP-DEL-T3",
        )
    return await get_current_user(credentials)


def require_roles(allowed_roles: list[str]) -> Callable:
    """
    RBAC dependency factory that asserts the current user possesses one of allowed_roles.
    """
    async def role_checker(user: UserTokenData = Depends(get_current_user)) -> UserTokenData:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User role '{user.role}' is not authorized. Requires one of: {allowed_roles}",
            )
        return user

    return role_checker
