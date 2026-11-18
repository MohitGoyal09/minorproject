"""JWT bearer authentication.

A seeded admin account comes from the environment, so a fresh deployment can log
in without a registration flow. Passwords are bcrypt hashes; tokens are HS256
JWTs carrying the user id and an expiry.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.accounting import User

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-secret-change-me-before-deploying")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_ROLE = "ADMIN"

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, email: str, expires_minutes: Optional[int] = None) -> str:
    minutes = ACCESS_TOKEN_EXPIRE_MINUTES if expires_minutes is None else expires_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise _credentials_error() from exc


def ensure_default_admin(db: Session) -> Optional[User]:
    """Create the admin from the environment when the user table is empty.

    If other users already exist, this does nothing: a real deployment manages
    its own accounts and the seed must not shadow them.
    """
    email = ADMIN_EMAIL.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing
    if db.query(User).count() > 0:
        return None

    user = User(email=email, password_hash=hash_password(ADMIN_PASSWORD), role=ADMIN_ROLE)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> Optional[User]:
    ensure_default_admin(db)
    user = db.query(User).filter(User.email == (email or "").strip().lower()).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password or "", user.password_hash):
        return None
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _credentials_error()

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not user or not user.is_active:
        raise _credentials_error()
    return user
