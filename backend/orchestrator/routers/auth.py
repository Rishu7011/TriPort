"""
Authentication Router — /api/v1/auth/*

Endpoints:
  - POST /api/v1/auth/login  -> Authenticate credentials and return JWT bearer token
  - GET  /api/v1/auth/me     -> Return active user identity & permissions
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from backend.orchestrator.auth.security import (
    DEMO_USERS,
    verify_password,
    create_access_token,
    UserTokenData,
)
from backend.orchestrator.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    role: str
    badge_number: str
    checkpoint_id: str
    permissions: list[str]


def _get_permissions(role: str) -> list[str]:
    """Map role to granular permissions."""
    base_perms = ["document:upload", "document:view", "decision:record"]
    if role == "officer":
        return base_perms
    if role == "supervisor":
        return base_perms + ["decision:override", "audit:view", "audit:verify"]
    if role == "auditor":
        return ["document:view", "audit:view", "audit:verify", "audit:export"]
    if role == "admin":
        return base_perms + ["decision:override", "audit:view", "audit:verify", "blacklist:manage", "system:configure"]
    return base_perms


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Authenticate officer or administrative user with email & password.
    """
    user_record = DEMO_USERS.get(req.email.lower().strip())
    if not user_record or not verify_password(req.password, user_record["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token_payload = {
        "sub": user_record["user_id"],
        "email": user_record["email"],
        "role": user_record["role"],
        "badge_number": user_record["badge_number"],
        "checkpoint_id": user_record["checkpoint_id"],
    }
    token = create_access_token(token_payload)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user={
            "user_id": user_record["user_id"],
            "email": user_record["email"],
            "role": user_record["role"],
            "name": user_record["name"],
            "badge_number": user_record["badge_number"],
            "checkpoint_id": user_record["checkpoint_id"],
            "permissions": _get_permissions(user_record["role"]),
        },
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: UserTokenData = Depends(get_current_user)):
    """
    Fetch authenticated user identity and effective permission set.
    """
    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        badge_number=user.badge_number,
        checkpoint_id=user.checkpoint_id,
        permissions=_get_permissions(user.role),
    )
