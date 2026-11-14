"""Metric history queries: time ranges, series, server comparison."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import MetricSample, Server, User
from app.schemas import SamplePoint, SeriesOut

router = APIRouter(prefix="/metrics", tags=["metrics"])

MAX_POINTS = 2000
KINDS = ("cpu", "memory", "disk", "net", "system")


def _series(
    db: Session,
    server_id: str,
    kind: str,
    name: str,
    date_from: datetime | None,
    date_to: datetime | None,
    limit: int,
) -> SeriesOut:
    if db.get(Server, server_id) is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    query = db.query(MetricSample).filter(
        MetricSample.server_id == server_id,
        MetricSample.kind == kind,
        MetricSample.name == name,
    )
    if date_from:
        query = query.filter(MetricSample.ts >= date_from)
    if date_to:
        query = query.filter(MetricSample.ts <= date_to)
    rows = query.order_by(MetricSample.ts.desc()).limit(limit).all()
    points = [SamplePoint(ts=r.ts, value=r.value) for r in reversed(rows)]
    return SeriesOut(server_id=server_id, kind=kind, name=name, points=points)


@router.get("/series", response_model=SeriesOut)
def get_series(
    server_id: str = Query(...),
    kind: str = Query(...),
    name: str = Query(...),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=MAX_POINTS),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> SeriesOut:
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {list(KINDS)}")
    return _series(db, server_id, kind, name, date_from, date_to, limit)


@router.get("/latest", response_model=list[dict])
def latest_values(
    server_id: str = Query(...),
    kind: str = Query(...),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Newest value per metric name (gauges, disks, interfaces)."""
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {list(KINDS)}")
    if db.get(Server, server_id) is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    rows = (
        db.query(MetricSample)
        .filter(MetricSample.server_id == server_id, MetricSample.kind == kind)
        .order_by(MetricSample.ts.desc(), MetricSample.id.desc())
        .limit(2000)
        .all()
    )
    seen: dict[str, MetricSample] = {}
    for row in rows:
        seen.setdefault(row.name, row)
    return [
        {"name": name, "ts": r.ts.isoformat() if r.ts else None, "value": r.value}
        for name, r in sorted(seen.items())
    ]


@router.get("/compare", response_model=list[SeriesOut])
def compare_servers(
    server_ids: str = Query(..., description="comma-separated server ids"),
    kind: str = Query(...),
    name: str = Query(...),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=MAX_POINTS),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> list[SeriesOut]:
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {list(KINDS)}")
    ids = [s.strip() for s in server_ids.split(",") if s.strip()][:8]
    if not ids:
        raise HTTPException(status_code=400, detail="Provide at least one server id.")
    return [_series(db, sid, kind, name, date_from, date_to, limit) for sid in ids]
