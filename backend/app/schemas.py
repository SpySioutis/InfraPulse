"""Pydantic request/response schemas with server-side validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Auth ----------------------------------------------------------------------


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: str
    username: str
    is_admin: bool

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    is_admin: bool = False


# --- Groups ----------------------------------------------------------------------


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None


class GroupOut(BaseModel):
    id: str
    name: str
    description: str | None
    server_count: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Servers -----------------------------------------------------------------------


class ServerIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    hostname: str = Field(min_length=1, max_length=253)
    ip_address: str | None = Field(default=None, max_length=64)
    environment: str | None = Field(default=None, max_length=64)
    group_id: str | None = None
    is_favorite: bool = False


class ServerOut(BaseModel):
    id: str
    name: str
    hostname: str
    ip_address: str | None
    os_name: str | None
    os_version: str | None
    architecture: str | None
    environment: str | None
    group_id: str | None
    group_name: str | None = None
    is_favorite: bool
    health: str = "unknown"
    health_reasons: list[str] = []
    agent_status: str | None = None
    agent_version: str | None = None
    last_heartbeat_at: datetime | None = None
    cpu_pct: float | None = None
    mem_pct: float | None = None
    disk_max_pct: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ServerPage(BaseModel):
    items: list[ServerOut]
    total: int
    page: int
    page_size: int
    pages: int


# --- Agents --------------------------------------------------------------------------


class RegistrationOut(BaseModel):
    server_id: str
    registration_token: str
    expires_at: datetime
    note: str = "Single-use. Shown once — store it on the monitored host now."


class AgentRegisterIn(BaseModel):
    registration_token: str = Field(min_length=8)
    agent_version: str = Field(min_length=1, max_length=64)


class AgentTokenOut(BaseModel):
    agent_token: str
    note: str = "Shown once — store it in the agent config now. It cannot be retrieved later."


class AgentOut(BaseModel):
    id: str
    server_id: str
    server_name: str | None = None
    status: str
    version: str | None
    token_prefix: str
    last_heartbeat_at: datetime | None = None
    last_metric_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Metrics (agent payload) ------------------------------------------------------------------


class CpuReport(BaseModel):
    total_pct: float = Field(ge=0, le=100)
    per_core: list[float] = Field(default_factory=list)
    count: int = Field(ge=1, le=1024)
    load_avg_1: float | None = Field(default=None, ge=0)
    load_avg_5: float | None = Field(default=None, ge=0)
    load_avg_15: float | None = Field(default=None, ge=0)


class MemReport(BaseModel):
    total_bytes: int = Field(ge=0)
    used_bytes: int = Field(ge=0)
    available_bytes: int = Field(ge=0)
    free_bytes: int = Field(ge=0)
    used_pct: float = Field(ge=0, le=100)
    swap_total_bytes: int = Field(ge=0, default=0)
    swap_used_bytes: int = Field(ge=0, default=0)


class DiskReport(BaseModel):
    filesystem: str = Field(min_length=1, max_length=256)
    mount: str = Field(min_length=1, max_length=1024)
    total_bytes: int = Field(ge=0)
    used_bytes: int = Field(ge=0)
    available_bytes: int = Field(ge=0)
    used_pct: float = Field(ge=0, le=100)


class NetReport(BaseModel):
    interface: str = Field(min_length=1, max_length=128)
    rx_bytes: int = Field(ge=0)
    tx_bytes: int = Field(ge=0)
    rx_packets: int = Field(ge=0)
    tx_packets: int = Field(ge=0)
    rx_errors: int = Field(ge=0)
    tx_errors: int = Field(ge=0)


class SystemReport(BaseModel):
    os_name: str = Field(min_length=1, max_length=128)
    os_version: str | None = Field(default=None, max_length=128)
    kernel: str | None = Field(default=None, max_length=256)
    architecture: str | None = Field(default=None, max_length=64)
    uptime_seconds: int = Field(ge=0)
    boot_time: datetime | None = None


class MetricReport(BaseModel):
    agent_version: str = Field(min_length=1, max_length=64)
    collected_at: datetime
    cpu: CpuReport
    memory: MemReport
    disks: list[DiskReport] = Field(default_factory=list, max_length=64)
    network: list[NetReport] = Field(default_factory=list, max_length=64)
    system: SystemReport


class HeartbeatIn(BaseModel):
    agent_version: str | None = Field(default=None, max_length=64)


# --- Metric queries ----------------------------------------------------------------------


class SamplePoint(BaseModel):
    ts: datetime
    value: float


class SeriesOut(BaseModel):
    server_id: str
    kind: str
    name: str
    points: list[SamplePoint]


# --- Alerts ------------------------------------------------------------------------------


class AlertRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    server_id: str | None = None
    metric: str = Field(min_length=1, max_length=64)
    operator: Literal[">", ">=", "<", "<="] = ">"
    threshold: float
    severity: Literal["informational", "warning", "critical"] = "warning"
    cooldown_minutes: int = Field(default=30, ge=1, le=1440)
    enabled: bool = True


class AlertRuleOut(BaseModel):
    id: str
    name: str
    server_id: str | None
    metric: str
    operator: str
    threshold: float
    severity: str
    cooldown_minutes: int
    enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: str
    rule_id: str | None
    server_id: str
    server_name: str | None = None
    alert_type: str
    severity: str
    message: str
    metric_value: float | None
    status: str
    triggered_at: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int
    page: int
    page_size: int
    pages: int


# --- Notifications ---------------------------------------------------------------------------------


class NotificationOut(BaseModel):
    id: str
    kind: str
    title: str
    body: str | None
    read_at: datetime | None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Dashboard ----------------------------------------------------------------------------------------------


class DashboardSummary(BaseModel):
    servers: int
    online: int
    offline: int
    warning: int
    critical: int
    groups: int
    active_alerts: int
    avg_cpu_pct: float | None = None
    avg_mem_pct: float | None = None
    total_disk_bytes: int = 0
    total_disk_used_bytes: int = 0
    recent_alerts: list[AlertOut] = []
    recent_activity: list[dict] = []


class AuditEntry(BaseModel):
    id: str
    username: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    detail: str | None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
