"""Metric ingestion: validate, expand, batch-insert, evaluate, retain.

One agent report becomes many MetricSample rows (totals, per-core,
per-filesystem, per-interface counters). Network throughput (rx_bps/tx_bps)
is derived from counter differences against the previous sample —
cumulative counters are never presented as throughput.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert
from sqlalchemy.orm import Session

from app import alerting, health as health_mod
from app.config import settings
from app.models import Agent, MetricSample, Server
from app.schemas import MetricReport


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _last_counter(
    db: Session, server_id: str, kind: str, name: str
) -> tuple[datetime, float] | None:
    row = (
        db.query(MetricSample.ts, MetricSample.value)
        .filter(
            MetricSample.server_id == server_id,
            MetricSample.kind == kind,
            MetricSample.name == name,
        )
        .order_by(MetricSample.ts.desc(), MetricSample.id.desc())
        .first()
    )
    if row is None:
        return None
    return _aware(row[0]), row[1]


def build_rows(
    db: Session,
    server_id: str,
    report: MetricReport,
    collected_at: datetime,
) -> list[dict]:
    """Expand an agent report into sample rows (throughput derived)."""
    rows: list[dict] = []

    def add(kind: str, name: str, value: float) -> None:
        rows.append({"server_id": server_id, "ts": collected_at, "kind": kind, "name": name, "value": float(value)})

    cpu, mem, sys = report.cpu, report.memory, report.system
    add("cpu", "total", cpu.total_pct)
    add("cpu", "count", float(cpu.count))
    for index, pct in enumerate(report.cpu.per_core):
        add("cpu", f"core-{index}", pct)
    if cpu.load_avg_1 is not None:
        add("cpu", "load_1", cpu.load_avg_1)
    if cpu.load_avg_5 is not None:
        add("cpu", "load_5", cpu.load_avg_5)
    if cpu.load_avg_15 is not None:
        add("cpu", "load_15", cpu.load_avg_15)

    add("memory", "total_bytes", float(mem.total_bytes))
    add("memory", "used_bytes", float(mem.used_bytes))
    add("memory", "available_bytes", float(mem.available_bytes))
    add("memory", "free_bytes", float(mem.free_bytes))
    add("memory", "used_pct", mem.used_pct)
    add("memory", "swap_total_bytes", float(mem.swap_total_bytes))
    add("memory", "swap_used_bytes", float(mem.swap_used_bytes))

    for disk in report.disks:
        prefix = f"disk/{disk.mount}"
        add("disk", f"{disk.mount}/total_bytes", float(disk.total_bytes))
        add("disk", f"{disk.mount}/used_bytes", float(disk.used_bytes))
        add("disk", f"{disk.mount}/available_bytes", float(disk.available_bytes))
        add("disk", f"{disk.mount}/used_pct", disk.used_pct)

    for net in report.network:
        base = f"net/{net.interface}"
        for field in ("rx_bytes", "tx_bytes", "rx_packets", "tx_packets", "rx_errors", "tx_errors"):
            current = float(getattr(net, field))
            add("net", f"{net.interface}/{field}", current)
            if field in ("rx_bytes", "tx_bytes") and current is not None:
                previous = _last_counter(db, server_id, "net", f"{net.interface}/{field}")
                if previous is not None:
                    prev_ts, prev_value = previous
                    elapsed = (collected_at - prev_ts).total_seconds()
                    delta = current - prev_value
                    if elapsed > 0 and 0 <= delta < 10**15:
                        direction = "rx_bps" if field == "rx_bytes" else "tx_bps"
                        rows.append(
                            {
                                "server_id": server_id,
                                "ts": collected_at,
                                "kind": "net",
                                "name": f"{net.interface}/{direction}",
                                "value": delta / elapsed,
                            }
                        )
    add("system", "uptime_seconds", float(sys.uptime_seconds))
    return rows


def maybe_retain(db: Session) -> int:
    """Delete samples older than the retention window (probabilistic, cheap)."""
    if random.random() > 0.05:
        return 0
    from datetime import timedelta

    cutoff = utcnow() - timedelta(days=settings.metric_retention_days)
    result = db.execute(delete(MetricSample).where(MetricSample.ts < cutoff))
    db.commit()
    return result.rowcount or 0


def ingest(db: Session, server: Server, agent: Agent, report: MetricReport) -> dict:
    """Store one report, refresh heartbeats/system info, evaluate alerts."""
    collected_at = _aware(report.collected_at)
    now = utcnow()
    rows = build_rows(db, server.id, report, collected_at)
    if rows:
        db.execute(insert(MetricSample), rows)

    agent.last_heartbeat_at = now
    agent.last_metric_at = now
    agent.version = report.agent_version
    agent.status = "online"
    server.os_name = report.system.os_name
    server.os_version = report.system.os_version
    server.architecture = report.system.architecture
    # Note: agents never overwrite inventory fields (name, IP, group).
    db.commit()

    latest = health_mod.latest_by_kind(
        db.query(MetricSample)
        .filter(MetricSample.server_id == server.id)
        .order_by(MetricSample.ts.desc(), MetricSample.id.desc())
        .limit(2000)
        .all()
    )
    outcome = alerting.evaluate_server(db, server, latest)
    alerting.evaluate_offline(db, server, agent.last_heartbeat_at)
    deleted = maybe_retain(db)
    return {"samples": len(rows), "alerts_fired": outcome["fired"], "alerts_resolved": outcome["resolved"], "expired_deleted": deleted}
