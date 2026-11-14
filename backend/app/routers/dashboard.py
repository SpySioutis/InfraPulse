"""Infrastructure overview computed from stored records only."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import auth, health as health_mod
from app.database import get_db
from app.models import Alert, AuditEvent, MetricSample, Server, ServerGroup, User
from app.routers.servers import server_health
from app.schemas import AlertOut, DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _latest_map(db: Session, server_id: str) -> dict[str, float]:
    samples = (
        db.query(MetricSample)
        .filter(MetricSample.server_id == server_id)
        .order_by(MetricSample.ts.desc(), MetricSample.id.desc())
        .limit(2000)
        .all()
    )
    return health_mod.latest_by_kind(samples)


@router.get("/summary", response_model=DashboardSummary)
def summary(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)) -> DashboardSummary:
    now = datetime.now(timezone.utc)
    servers = db.query(Server).all()
    groups = db.query(func.count(ServerGroup.id)).scalar() or 0

    online = offline = warning = critical = 0
    cpu_values: list[float] = []
    mem_values: list[float] = []
    total_disk = total_disk_used = 0
    for server in servers:
        status, _, _ = server_health(db, server)
        if status == "healthy":
            online += 1
        elif status == "offline":
            offline += 1
        elif status == "warning":
            warning += 1
        elif status == "critical":
            critical += 1
        else:
            offline += 1  # unknown counts as not-online
        latest = _latest_map(db, server.id)
        if latest.get("cpu/total") is not None:
            cpu_values.append(latest["cpu/total"])
        if latest.get("memory/used_pct") is not None:
            mem_values.append(latest["memory/used_pct"])
        disks_total = [v for k, v in latest.items() if k.endswith("/total_bytes") and k.startswith("disk/")]
        disks_used = [v for k, v in latest.items() if k.endswith("/used_bytes") and k.startswith("disk/")]
        total_disk += int(sum(disks_total))
        total_disk_used += int(sum(disks_used))

    active_alerts = (
        db.query(func.count(Alert.id)).filter(Alert.status.in_(["active", "acknowledged"])).scalar() or 0
    )
    recent_rows = db.query(Alert).order_by(Alert.triggered_at.desc()).limit(8).all()
    recent = []
    for alert in recent_rows:
        payload = AlertOut.model_validate(alert)
        server = db.get(Server, alert.server_id)
        payload.server_name = server.name if server else None
        recent.append(payload)

    activity = [
        {
            "id": a.id,
            "username": a.username,
            "action": a.action,
            "detail": a.detail,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(10).all()
    ]

    return DashboardSummary(
        servers=len(servers),
        online=online,
        offline=offline,
        warning=warning,
        critical=critical,
        groups=groups,
        active_alerts=active_alerts,
        avg_cpu_pct=round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else None,
        avg_mem_pct=round(sum(mem_values) / len(mem_values), 1) if mem_values else None,
        total_disk_bytes=total_disk,
        total_disk_used_bytes=total_disk_used,
        recent_alerts=recent,
        recent_activity=activity,
    )
