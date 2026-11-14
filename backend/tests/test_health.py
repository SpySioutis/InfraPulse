"""Health evaluation unit tests (pure logic, no DB)."""

from app import health
from app.config import settings


def test_offline_when_heartbeat_stale():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    assert health.is_heartbeat_stale(None, now) is True
    assert health.is_heartbeat_stale(now - timedelta(seconds=10000), now) is True
    assert health.is_heartbeat_stale(now, now) is False


def test_unknown_without_samples():
    status, reasons = health.evaluate_health({}, heartbeat_stale=False)
    assert status == "unknown"
    assert reasons


def test_healthy_when_everything_normal():
    latest = {"cpu/total": 10.0, "memory/used_pct": 20.0, "disk//used_pct": 30.0}
    assert health.evaluate_health(latest, False)[0] == "healthy"


def test_warning_and_critical_thresholds():
    warn_cpu = {"cpu/total": settings.cpu_warn_pct + 1}
    assert health.evaluate_health(warn_cpu, False)[0] == "warning"
    crit_cpu = {"cpu/total": settings.cpu_crit_pct + 1}
    status, reasons = health.evaluate_health(crit_cpu, False)
    assert status == "critical" and reasons
    worst_disk = {"disk//used_pct": 10.0, "disk//data/used_pct": settings.disk_crit_pct + 1}
    assert health.evaluate_health(worst_disk, False)[0] == "critical"


def test_offline_beats_everything():
    latest = {"cpu/total": 99.9}
    assert health.evaluate_health(latest, True)[0] == "offline"
