-- 0001_initial: users, groups, servers, agents, registration tokens,
-- metric samples, alert rules, alerts, notifications, audit events.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(128) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS server_groups (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(256) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS servers (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(256) NOT NULL UNIQUE,
    hostname VARCHAR(253) NOT NULL,
    ip_address VARCHAR(64),
    os_name VARCHAR(128),
    os_version VARCHAR(128),
    architecture VARCHAR(64),
    environment VARCHAR(64),
    group_id VARCHAR(36) REFERENCES server_groups (id) ON DELETE SET NULL,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_servers_group_id ON servers (group_id);

CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR(36) PRIMARY KEY,
    server_id VARCHAR(36) NOT NULL UNIQUE REFERENCES servers (id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    token_prefix VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    version VARCHAR(64),
    last_heartbeat_at TIMESTAMPTZ,
    last_metric_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_agents_server_id ON agents (server_id);

CREATE TABLE IF NOT EXISTS registration_tokens (
    id VARCHAR(36) PRIMARY KEY,
    server_id VARCHAR(36) NOT NULL REFERENCES servers (id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    token_prefix VARCHAR(16) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_registration_tokens_server_id ON registration_tokens (server_id);

CREATE TABLE IF NOT EXISTS metric_samples (
    id BIGSERIAL PRIMARY KEY,
    server_id VARCHAR(36) NOT NULL REFERENCES servers (id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    kind VARCHAR(32) NOT NULL,
    name VARCHAR(256) NOT NULL,
    value DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_metric_samples_lookup
    ON metric_samples (server_id, kind, name, ts DESC);

CREATE TABLE IF NOT EXISTS alert_rules (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    server_id VARCHAR(36) REFERENCES servers (id) ON DELETE CASCADE,
    metric VARCHAR(64) NOT NULL,
    operator VARCHAR(8) NOT NULL DEFAULT '>',
    threshold DOUBLE PRECISION NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'warning',
    cooldown_minutes INTEGER NOT NULL DEFAULT 30,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_alert_rules_server_id ON alert_rules (server_id);

CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(36) PRIMARY KEY,
    rule_id VARCHAR(36) REFERENCES alert_rules (id) ON DELETE SET NULL,
    server_id VARCHAR(36) NOT NULL REFERENCES servers (id) ON DELETE CASCADE,
    alert_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    message TEXT NOT NULL,
    metric_value DOUBLE PRECISION,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    last_notified_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_alerts_server_id ON alerts (server_id);
CREATE INDEX IF NOT EXISTS ix_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS ix_alerts_triggered_at ON alerts (triggered_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users (id) ON DELETE CASCADE,
    kind VARCHAR(32) NOT NULL,
    title VARCHAR(256) NOT NULL,
    body TEXT,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at DESC);

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    username VARCHAR(256),
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64),
    entity_id VARCHAR(36),
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events (created_at DESC);
