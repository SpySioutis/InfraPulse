"""Server inventory CRUD with server-side filtering and live health."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth, health as health_mod
from app.database import get_db
from app.models import MetricSample, Server, ServerGroup, User
from app.schemas import ServerIn, ServerOut, ServerPage

router = APIRouter(prefix="/servers", tags=["servers"])

MAX_PAGE_SIZE = 100


def server_health(db: Session, server: Server) -> tuple[str, list[str], dict[str, float | None]]:
    from datetime import datetime, timezone

    agent = server.agent
    heartbeat = agent.last_heartbeat_at if agent else None
    now = datetime.now(timezone.utc)
    stale = health_mod.is_heartbeat_stale(heartbeat, now)
    samples = (
        db.query(MetricSample)
        .filter(MetricSample.server_id == server.id)
        .order_by(MetricSample.ts.desc(), MetricSample.id.desc())
        .limit(2000)
        .all()
    )
    latest = health_mod.latest_by_kind(samples)
    status, reasons = health_mod.evaluate_health(latest, stale)
    summary = {
        "cpu": latest.get("cpu/total"),
        "mem": latest.get("memory/used_pct"),
        "disk": max(
            [v for k, v in latest.items() if k.startswith("disk/") and k.endswith("/used_pct")],
            default=None,
        ),
    }
    return status, reasons, summary


def _out(db: Session, server: Server) -> ServerOut:
    payload = ServerOut.model_validate(server)
    payload.group_name = server.group.name if server.group else None
    status, reasons, summary = server_health(db, server)
    payload.health = status
    payload.health_reasons = reasons
    payload.cpu_pct = summary["cpu"]
    payload.mem_pct = summary["mem"]
    payload.disk_max_pct = summary["disk"]
    if server.agent:
        payload.agent_status = server.agent.status
        payload.agent_version = server.agent.version
        payload.last_heartbeat_at = server.agent.last_heartbeat_at
    return payload


@router.get("", response_model=ServerPage)
def list_servers(
    q: str | None = Query(default=None, max_length=256),
    group_id: str | None = Query(default=None),
    environment: str | None = Query(default=None, max_length=64),
    favorite: bool | None = Query(default=None),
    health: str | None = Query(default=None, max_length=16),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> ServerPage:
    query = db.query(Server)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Server.name.ilike(like), Server.hostname.ilike(like), Server.ip_address.ilike(like))
        )
    if group_id:
        query = query.filter(Server.group_id == group_id)
    if environment:
        query = query.filter(Server.environment == environment)
    if favorite is not None:
        query = query.filter(Server.is_favorite == favorite)
    total = query.with_entities(func.count(Server.id)).scalar() or 0
    rows = query.order_by(Server.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_out(db, s) for s in rows]
    if health:
        items = [i for i in items if i.health == health]
        total = len(items)
    pages = max(1, (total + page_size - 1) // page_size)
    return ServerPage(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=ServerOut, status_code=201)
def create_server(
    payload: ServerIn, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> ServerOut:
    if payload.group_id is not None and db.get(ServerGroup, payload.group_id) is None:
        raise HTTPException(status_code=404, detail="Server group not found.")
    server = Server(
        name=payload.name.strip(),
        hostname=payload.hostname.strip(),
        ip_address=payload.ip_address,
        environment=payload.environment,
        group_id=payload.group_id,
        is_favorite=payload.is_favorite,
    )
    db.add(server)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A server with this name already exists.")
    db.refresh(server)
    auth.audit(db, user, "server.create", "server", server.id, server.name)
    return _out(db, server)


@router.get("/{server_id}", response_model=ServerOut)
def get_server(
    server_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> ServerOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    return _out(db, server)


@router.put("/{server_id}", response_model=ServerOut)
def update_server(
    server_id: str,
    payload: ServerIn,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> ServerOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    if payload.group_id is not None and db.get(ServerGroup, payload.group_id) is None:
        raise HTTPException(status_code=404, detail="Server group not found.")
    server.name = payload.name.strip()
    server.hostname = payload.hostname.strip()
    server.ip_address = payload.ip_address
    server.environment = payload.environment
    server.group_id = payload.group_id
    server.is_favorite = payload.is_favorite
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A server with this name already exists.")
    db.refresh(server)
    auth.audit(db, user, "server.update", "server", server.id, server.name)
    return _out(db, server)


@router.delete("/{server_id}", status_code=204)
def delete_server(
    server_id: str, user: User = Depends(auth.require_admin), db: Session = Depends(get_db)
) -> None:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    db.delete(server)
    db.commit()
    auth.audit(db, user, "server.delete", "server", server_id, server.name)


@router.patch("/{server_id}/favorite", response_model=ServerOut)
def toggle_favorite(
    server_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> ServerOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    server.is_favorite = not server.is_favorite
    db.commit()
    db.refresh(server)
    return _out(db, server)
