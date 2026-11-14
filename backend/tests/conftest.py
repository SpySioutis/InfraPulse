"""Shared pytest fixtures: isolated SQLite DB, admin user."""

import os
import sys
from pathlib import Path

os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.setdefault("LOGIN_MAX_ATTEMPTS", "1000")
os.environ.setdefault("METRIC_RETENTION_DAYS", "30")
os.environ.setdefault("HEARTBEAT_GRACE_SECONDS", "180")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import auth as auth_module  # noqa: E402
from app import database as database_module  # noqa: E402
from app import models  # noqa: E402, F401
from app.auth import ensure_admin  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    ensure_admin(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    auth_module._attempts.clear()

    def override():
        try:
            yield db_session
        finally:
            pass

    class _SessionFactory:
        def __call__(self):
            return db_session

        def __enter__(self):
            return db_session

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(database_module, "SessionLocal", _SessionFactory())

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
