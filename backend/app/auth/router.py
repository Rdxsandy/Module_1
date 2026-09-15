"""
auth/router.py - Authentication endpoints.

POST /api/auth/login  - public, returns JWT
GET  /api/auth/me     - requires valid JWT
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.schemas import LoginRequest, TokenResponse, UserOut
from app.auth.security import verify_password, create_access_token
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return a signed JWT.
    Returns generic 401 for any invalid credentials (no leaking which field is wrong).
    """
    # Lookup by username
    user = db.query(User).filter(
        User.username == payload.username,
        User.is_active.is_(True)
    ).first()

    # Verify password - always run verify even if user not found to prevent timing attacks
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user info."""
    return current_user
