"""Server health evaluation. Single place where status is computed.

Health (documented in MANUAL.md):
- offline .... no heartbeat within HEARTBEAT_GRACE_SECONDS.
- unknown .... heartbeats OK but no metric samples yet.
- critical .. any *_crit threshold breached (cpu/mem/max disk).
- warning ... any *_warn threshold breached.
- healthy ... none of the above.

Thresholds come from settings (centralized config), never literals.
"""

from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.models import MetricSample


def is_heartbeat_stale(last_heartbeat: datetime | None, now: datetime) -> bool:
    if last_heartbeat is None:
        return True
    seen = last_heartbeat if last_heartbeat.tzinfo else last_heartbeat.replace(tzinfo=now.tzinfo)
    return (now - seen).total_seconds() > settings.heartbeat_grace_seconds


def latest_by_kind(samples: list[MetricSample]) -> dict[str, float]:
    """Newest value per (kind, name). Samples must be newest-first."""
    latest: dict[str, float] = {}
    for sample in samples:
        key = f"{sample.kind}/{sample.name}"
        if key not in latest:
            latest[key] = sample.value
    return latest


def evaluate_health(latest: dict[str, float], heartbeat_stale: bool) -> tuple[str, list[str]]:
    """Return (status, reasons). Pure function of thresholds + inputs."""
    if heartbeat_stale:
        return "offline", ["no heartbeat within grace period"]
    if not latest:
        return "unknown", ["no metric samples yet"]

    reasons: list[str] = []
    critical = False
    warning = False

    def check(label: str, value: float | None, warn: float, crit: float) -> None:
        nonlocal critical, warning
        if value is None:
            return
        if value >= crit:
            critical = True
            reasons.append(f"{label} {value:.1f}% >= critical {crit:.0f}%")
        elif value >= warn:
            warning = True
            reasons.append(f"{label} {value:.1f}% >= warning {warn:.0f}%")

    check("cpu", latest.get("cpu/total"), settings.cpu_warn_pct, settings.cpu_crit_pct)
    check("memory", latest.get("memory/used_pct"), settings.mem_warn_pct, settings.mem_crit_pct)
    disk_values = [v for k, v in latest.items() if k.startswith("disk/") and k.endswith("/used_pct")]
    if disk_values:
        worst = max(disk_values)
        check("disk (worst mount)", worst, settings.disk_warn_pct, settings.disk_crit_pct)

    if critical:
        return "critical", reasons
    if warning:
        return "warning", reasons
    return "healthy", []
