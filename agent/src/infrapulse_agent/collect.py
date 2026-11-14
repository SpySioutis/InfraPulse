"""Local system metric collection with psutil.

Only the documented metric families are collected: CPU, memory, disks,
network counters and basic system info. No shell commands, no remote
access, no process listing beyond aggregate counts.
"""

from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from typing import Any

import psutil

from infrapulse_agent.config import AGENT_VERSION


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Collector:
    """Stateful collector: primed once so cpu_percent() deltas are valid."""

    def __init__(self) -> None:
        self._primed = False

    def prime(self) -> None:
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
        except Exception:  # noqa: BLE001 - collection must never crash the agent
            pass
        self._primed = True

    def collect(self) -> dict[str, Any]:
        if not self._primed:
            self.prime()
        return {
            "agent_version": AGENT_VERSION,
            "collected_at": _utcnow_iso(),
            "cpu": self._cpu(),
            "memory": self._memory(),
            "disks": self._disks(),
            "network": self._network(),
            "system": self._system(),
        }

    def _cpu(self) -> dict[str, Any]:
        try:
            total = float(psutil.cpu_percent(interval=None))
        except Exception:  # noqa: BLE001
            total = 0.0
        try:
            per_core = [float(v) for v in psutil.cpu_percent(interval=None, percpu=True)]
        except Exception:  # noqa: BLE001
            per_core = []
        try:
            count = psutil.cpu_count(logical=True) or 1
        except Exception:  # noqa: BLE001
            count = 1
        load: dict[str, float | None] = {"load_avg_1": None, "load_avg_5": None, "load_avg_15": None}
        try:
            avg1, avg5, avg15 = os.getloadavg()
            load = {"load_avg_1": avg1, "load_avg_5": avg5, "load_avg_15": avg15}
        except (OSError, AttributeError):
            pass
        return {"total_pct": total, "per_core": per_core, "count": count, **load}

    def _memory(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        try:
            swap = psutil.swap_memory()
            swap_total, swap_used = int(swap.total), int(swap.used)
        except Exception:  # noqa: BLE001
            swap_total, swap_used = 0, 0
        return {
            "total_bytes": int(vm.total),
            "used_bytes": int(vm.used),
            "available_bytes": int(vm.available),
            "free_bytes": int(vm.free),
            "used_pct": float(vm.percent),
            "swap_total_bytes": swap_total,
            "swap_used_bytes": swap_used,
        }

    def _disks(self) -> list[dict[str, Any]]:
        disks: list[dict[str, Any]] = []
        try:
            partitions = psutil.disk_partitions(all=False)
        except Exception:  # noqa: BLE001
            return disks
        seen: set[str] = set()
        for part in partitions:
            if part.mountpoint in seen:
                continue
            seen.add(part.mountpoint)
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            total = int(usage.total)
            disks.append({
                "filesystem": part.device or "unknown",
                "mount": part.mountpoint,
                "total_bytes": total,
                "used_bytes": int(usage.used),
                "available_bytes": int(usage.free),
                "used_pct": round(100.0 * usage.used / total, 1) if total else 0.0,
            })
        return disks

    def _network(self) -> list[dict[str, Any]]:
        interfaces: list[dict[str, Any]] = []
        try:
            counters = psutil.net_io_counters(pernic=True) or {}
        except Exception:  # noqa: BLE001
            return interfaces
        for name in sorted(counters):
            stats = counters[name]
            interfaces.append({
                "interface": name,
                "rx_bytes": int(stats.bytes_recv),
                "tx_bytes": int(stats.bytes_sent),
                "rx_packets": int(stats.packets_recv),
                "tx_packets": int(stats.packets_sent),
                "rx_errors": int(stats.errin),
                "tx_errors": int(stats.errout),
            })
        return interfaces

    def _system(self) -> dict[str, Any]:
        uname = platform.uname()
        try:
            boot = float(psutil.boot_time())
        except Exception:  # noqa: BLE001
            boot = time.time()
        return {
            "os_name": uname.system or "Unknown",
            "os_version": uname.release or None,
            "kernel": uname.version or None,
            "architecture": uname.machine or None,
            "uptime_seconds": max(0, int(time.time() - boot)),
            "boot_time": datetime.fromtimestamp(boot, tz=timezone.utc).isoformat(),
        }
