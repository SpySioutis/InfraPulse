"""Alert rules, alerts, notifications, and manual evaluation."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import alerting, auth
from app.database import get_db
from app.models import Alert, AlertRule, Notification, Server, User
from app.schemas import AlertOut, AlertPage, AlertRuleIn, AlertRuleOut, NotificationOut

router = APIRouter(tags=["alerts"])

MAX_PAGE_SIZE = 200


def _alert_out(db: Session, alert: Alert) -> AlertOut:
    payload = AlertOut.model_validate(alert)
    server = db.get(Server, alert.server_id)
    payload.server_name = server.name if server else None
    return payload


# --- rules ---------------------------------------------------------------


@router.get("/alert-rules", response_model=list[AlertRuleOut])
def list_rules(
    server_id: str | None = Query(default=None),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertRule]:
    query = db.query(AlertRule)
    if server_id:
        query = query.filter(AlertRule.server_id == server_id)
    return query.order_by(AlertRule.created_at.desc()).all()


@router.post("/alert-rules", response_model=AlertRuleOut, status_code=201)
def create_rule(
    payload: AlertRuleIn,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> AlertRule:
    if payload.server_id is not None and db.get(Server, payload.server_id) is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    if not (
        payload.metric in ("cpu_total", "memory_used_pct", "disk_max_pct")
        or payload.metric.startswith("net_errs_")
        or "/" in payload.metric
    ):
        raise HTTPException(status_code=400, detail="Unknown metric. Use cpu_total, memory_used_pct, disk_max_pct, net_errs_<iface> or kind/name.")
    rule = AlertRule(
        name=payload.name.strip(),
        server_id=payload.server_id,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        severity=payload.severity,
        cooldown_minutes=payload.cooldown_minutes,
        enabled=payload.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    auth.audit(db, user, "alert_rule.create", "alert_rule", rule.id, rule.name)
    return rule


@router.put("/alert-rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(
    rule_id: str,
    payload: AlertRuleIn,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found.")
    if payload.server_id is not None and db.get(Server, payload.server_id) is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    rule.name = payload.name.strip()
    rule.server_id = payload.server_id
    rule.metric = payload.metric
    rule.operator = payload.operator
    rule.threshold = payload.threshold
    rule.severity = payload.severity
    rule.cooldown_minutes = payload.cooldown_minutes
    rule.enabled = payload.enabled
    db.commit()
    db.refresh(rule)
    auth.audit(db, user, "alert_rule.update", "alert_rule", rule.id, rule.name)
    return rule


@router.delete("/alert-rules/{rule_id}", status_code=204)
def delete_rule(
    rule_id: str, user: User = Depends(auth.require_admin), db: Session = Depends(get_db)
) -> None:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found.")
    db.delete(rule)
    db.commit()
    auth.audit(db, user, "alert_rule.delete", "alert_rule", rule_id, rule.name)


# --- alerts --------------------------------------------------------------


@router.get("/alerts", response_model=AlertPage)
def list_alerts(
    status: str | None = Query(default=None, max_length=16),
    severity: str | None = Query(default=None, max_length=16),
    server_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> AlertPage:
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)
    if server_id:
        query = query.filter(Alert.server_id == server_id)
    total = query.with_entities(func.count(Alert.id)).scalar() or 0
    items = (
        query.order_by(Alert.triggered_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    pages = max(1, (total + page_size - 1) // page_size)
    return AlertPage(
        items=[_alert_out(db, a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> AlertOut:
    from datetime import timezone

    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.status == "active":
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
        auth.audit(db, user, "alert.acknowledge", "alert", alert.id, alert.alert_type)
    return _alert_out(db, alert)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> AlertOut:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    alerting.resolve(db, alert)
    db.refresh(alert)
    auth.audit(db, user, "alert.resolve", "alert", alert.id, alert.alert_type)
    return _alert_out(db, alert)


@router.post("/alerts/evaluate")
def evaluate_all(
    user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Manual full evaluation (for cron/systemd timers). Also runs on ingest."""
    from app import health as health_mod
    from app.models import MetricSample

    checked = fired = resolved = 0
    for server in db.query(Server).all():
        samples = (
            db.query(MetricSample)
            .filter(MetricSample.server_id == server.id)
            .order_by(MetricSample.ts.desc(), MetricSample.id.desc())
            .limit(2000)
            .all()
        )
        latest = health_mod.latest_by_kind(samples)
        outcome = alerting.evaluate_server(db, server, latest)
        checked += 1
        fired += outcome["fired"]
        resolved += outcome["resolved"]
        heartbeat = server.agent.last_heartbeat_at if server.agent else None
        before = alerting.active_alert(db, server.id, "offline")
        alerting.evaluate_offline(db, server, heartbeat)
        if before is None and alerting.active_alert(db, server.id, "offline") is not None:
            fired += 1
    return {"servers_checked": checked, "alerts_fired": fired, "alerts_resolved": resolved}


# --- notifications -------------------------------------------------------


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    from app.models import Notification

    query = db.query(Notification).order_by(Notification.created_at.desc())
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return query.limit(limit).all()


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: str,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> NotificationOut:
    from datetime import timezone

    from app.models import Notification

    note = db.get(Notification, notification_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(note)
    return note


@router.post("/notifications/read-all")
def mark_all_read(
    user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> dict:
    from datetime import timezone

    from app.models import Notification

    count = (
        db.query(Notification)
        .filter(Notification.read_at.is_(None))
        .update({"read_at": datetime.now(timezone.utc)})
    )
    db.commit()
    return {"marked": count}
