"""User login, profile, admin user management."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth, security
from app.database import get_db
from app.models import User
from app.schemas import LoginIn, TokenOut, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    client_ip = request.client.host if request.client else "unknown"
    if not auth.login_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )
    auth.record_login_attempt(client_ip)
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    auth.audit(db, user, "login")
    return TokenOut(
        access_token=security.create_token(user.id, user.username, user.is_admin),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(auth.get_current_user)) -> User:
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(_admin: User = Depends(auth.require_admin), db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.username).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    admin: User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = User(
        username=payload.username.strip(),
        password_hash=security.hash_password(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists.")
    db.refresh(user)
    auth.audit(db, admin, "user.create", "user", user.id, f"username={user.username}")
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    admin: User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    db.delete(user)
    db.commit()
    auth.audit(db, admin, "user.delete", "user", user_id, f"username={user.username}")
