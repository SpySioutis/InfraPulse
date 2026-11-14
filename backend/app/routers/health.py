"""Health check + public configuration (no secrets)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "infrapulse-backend"}


@router.get("/config")
def public_config() -> dict:
    return {
        "cpu_warn_pct": settings.cpu_warn_pct,
        "cpu_crit_pct": settings.cpu_crit_pct,
        "mem_warn_pct": settings.mem_warn_pct,
        "mem_crit_pct": settings.mem_crit_pct,
        "disk_warn_pct": settings.disk_warn_pct,
        "disk_crit_pct": settings.disk_crit_pct,
        "heartbeat_grace_seconds": settings.heartbeat_grace_seconds,
        "metric_retention_days": settings.metric_retention_days,
    }
