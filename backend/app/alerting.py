"""Alert evaluation with incident deduplication.

- Threshold rules fire when the latest value breaches operator/threshold.
- Cooldown: a rule does not re-fire while its alert is active, nor within
  cooldown_minutes of the last notification for the same incident.
- Offline alerts fire when the heartbeat goes stale with no active offline
  alert for the server; they auto-resolve on the next successful ingest.
- Resolution: when the breaching condition clears (or heartbeat returns),
  the active alert moves to resolved with resolved_at set.
"""

from __future__ import annotations

import operator
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import health as health_mod
from app.config import settings
from app.models import Alert, AlertRule, MetricSample, Notification, Server

OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _metric_value(latest: dict[str, float], metric: str) -> float | None:
    """Resolve a rule metric to the newest stored value.

    Supported rule metrics: cpu_total, memory_used_pct, disk_max_pct,
    net_errs_<iface>, or an exact kind/name key like 'cpu/total'.
    """
    if metric == "cpu_total":
        return latest.get("cpu/total")
    if metric == "memory_used_pct":
        return latest.get("memory/used_pct")
    if metric == "disk_max_pct":
        disks = [v for k, v in latest.items() if k.startswith("disk/") and k.endswith("/used_pct")]
        return max(disks) if disks else None
    if metric.startswith("net_errs_"):
        iface = metric[len("net_errs_"):]
        errs_in = latest.get(f"net/{iface}/rx_errs")
        errs_out = latest.get(f"net/{iface}/tx_errs")
        if errs_in is None and errs_out is None:
            return None
        return (errs_in or 0) + (errs_out or 0)
    return latest.get(metric)


def _notify(db: Session, title: str, body: str) -> None:
    db.add(Notification(kind="alert", title=title, body=body))


def active_alert(db: Session, server_id: str, alert_type: str) -> Alert | None:
    return (
        db.query(Alert)
        .filter(
            Alert.server_id == server_id,
            Alert.alert_type == alert_type,
            Alert.status.in_(["active", "acknowledged"]),
        )
        .order_by(Alert.triggered_at.desc())
        .first()
    )


def fire(
    db: Session,
    server: Server,
    alert_type: str,
    severity: str,
    message: str,
    rule_id: str | None = None,
    metric_value: float | None = None,
    cooldown_minutes: int = 30,
) -> Alert | None:
    """Fire unless an incident is already open (or notified within cooldown)."""
    existing = active_alert(db, server.id, alert_type)
    now = utcnow()
    if existing is not None:
        if existing.last_notified_at and now - _aware(existing.last_notified_at) < timedelta(minutes=cooldown_minutes):
            return None  # still in cooldown; incident already tracked
        existing.last_notified_at = now
        existing.metric_value = metric_value if metric_value is not None else existing.metric_value
        db.commit()
        return existing
    alert = Alert(
        rule_id=rule_id,
        server_id=server.id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        metric_value=metric_value,
        last_notified_at=now,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    _notify(db, f"[{severity.upper()}] {server.name}: {alert_type}", message)
    db.commit()
    return alert


def resolve(db: Session, alert: Alert) -> None:
    if alert.status in ("active", "acknowledged"):
        alert.status = "resolved"
        alert.resolved_at = utcnow()
        db.commit()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def evaluate_server(db: Session, server: Server, latest: dict[str, float]) -> dict:
    """Evaluate threshold rules + resolve cleared incidents for one server."""
    rules = (
        db.query(AlertRule)
        .filter(AlertRule.enabled == True)  # noqa: E712
        .filter((AlertRule.server_id == server.id) | (AlertRule.server_id.is_(None)))
        .all()
    )
    fired = 0
    resolved = 0
    for rule in rules:
        op = OPS.get(rule.operator)
        if op is None:
            continue
        value = _metric_value(latest, rule.metric)
        alert_type = f"rule:{rule.id}"
        existing = active_alert(db, server.id, alert_type)
        if value is not None and op(value, rule.threshold):
            message = f"{rule.name}: {rule.metric} is {value:.2f} ({rule.operator} {rule.threshold})"
            if fire(
                db,
                server,
                alert_type,
                rule.severity,
                message,
                rule_id=rule.id,
                metric_value=value,
                cooldown_minutes=rule.cooldown_minutes,
            ) is not None and existing is None:
                fired += 1
        elif existing is not None:
            resolve(db, existing)
            resolved += 1

    return {"fired": fired, "resolved": resolved}


def evaluate_offline(db: Session, server: Server, agent_last_heartbeat) -> str | None:
    """Fire or resolve the offline incident. Returns the alert id or None."""
    now = utcnow()
    stale = health_mod.is_heartbeat_stale(agent_last_heartbeat, now)
    existing = active_alert(db, server.id, "offline")
    if stale:
        alert = fire(
            db,
            server,
            "offline",
            "critical",
            f"{server.name} is offline: no heartbeat within {settings.heartbeat_grace_seconds}s.",
            cooldown_minutes=60,
        )
        return alert.id if alert else (existing.id if existing else None)
    if existing is not None:
        resolve(db, existing)
    return None
