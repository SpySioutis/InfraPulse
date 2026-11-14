"""Authentication dependencies: bearer tokens, admin bootstrap, rate limit."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import security
from app.config import settings
from app.database import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)

_attempts: defaultdict[str, list[float]] = defaultdict(list)


def login_allowed(client_ip: str) -> bool:
    now = time.monotonic()
    recent = [t for t in _attempts[client_ip] if now - t < settings.login_window_seconds]
    _attempts[client_ip] = recent
    return len(recent) < settings.login_max_attempts


def record_login_attempt(client_ip: str) -> None:
    _attempts[client_ip].append(time.monotonic())


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    payload = security.decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")
    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")
    request.state.user = user
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    return user


def ensure_admin(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    username = settings.admin_username.strip()
    password = settings.admin_password
    if not username or not password:
        raise RuntimeError(
            "No users exist and ADMIN_USERNAME/ADMIN_PASSWORD are not set. "
            "Set them in .env (see .env.example) and restart."
        )
    db.add(User(username=username, password_hash=security.hash_password(password), is_admin=True))
    db.commit()


def audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: str | None = None,
) -> None:
    from app.models import AuditEvent

    db.add(
        AuditEvent(
            user_id=user.id if user else None,
            username=user.username if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
        )
    )
    db.commit()
