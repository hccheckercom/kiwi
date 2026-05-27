"""JWT Authentication for Kiwi Dashboard."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel


# JWT Configuration
SECRET_KEY = os.environ.get("KIWI_JWT_SECRET", "kiwi-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Security scheme
security = HTTPBearer()


class User(BaseModel):
    username: str
    role: str = "admin"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_HOURS * 3600


# In-memory user store (replace with database in production)
# Lazy-load hashed password to avoid bcrypt initialization issues
USERS = {
    "admin": {
        "username": "admin",
        "hashed_password": None,  # Will be set on first access
        "role": "admin",
    }
}

def _ensure_admin_password():
    """Lazy-initialize admin password hash."""
    if USERS["admin"]["hashed_password"] is None:
        password = os.environ.get("KIWI_ADMIN_PASSWORD")
        if not password:
            raise ValueError(
                "KIWI_ADMIN_PASSWORD environment variable not set. "
                "Set it before starting the web server: export KIWI_ADMIN_PASSWORD=your_secure_password"
            )
        if len(password) > 72:
            password = password[:72]
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        USERS["admin"]["hashed_password"] = bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_user(username: str) -> Optional[dict]:
    """Get user from store."""
    return USERS.get(username)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Authenticate user with username and password."""
    _ensure_admin_password()
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Dependency to get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return User(username=user["username"], role=user["role"])


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user