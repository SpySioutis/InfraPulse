"""API integration tests: auth, servers, groups, agents, ingest, history."""


def auth_headers(client):
    resp = client.post("/api/auth/login", json={"username": "testadmin", "password": "testpassword123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_server(client, headers, name="web-1", **extra):
    payload = {"name": name, "hostname": "web-1.lan", "environment": "production"}
    payload.update(extra)
    resp = client.post("/api/servers", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def sample_report(version="1.0.0"):
    return {
        "agent_version": version,
        "collected_at": "2026-01-01T00:00:00Z",
        "cpu": {"total_pct": 12.5, "per_core": [10.0, 15.0], "count": 2,
                "load_avg_1": 0.5, "load_avg_5": 0.4, "load_avg_15": 0.3},
        "memory": {"total_bytes": 8000, "used_bytes": 4000, "available_bytes": 4000,
                   "free_bytes": 3000, "used_pct": 50.0,
                   "swap_total_bytes": 1000, "swap_used_bytes": 100},
        "disks": [{"filesystem": "/dev/sda1", "mount": "/", "total_bytes": 10000,
                   "used_bytes": 4000, "available_bytes": 6000, "used_pct": 40.0}],
        "network": [{"interface": "eth0", "rx_bytes": 1000, "tx_bytes": 2000,
                     "rx_packets": 10, "tx_packets": 20, "rx_errors": 0, "tx_errors": 1}],
        "system": {"os_name": "Linux", "os_version": "6.1", "kernel": "6.1.0",
                   "architecture": "x86_64", "uptime_seconds": 3600,
                   "boot_time": "2025-12-31T23:00:00Z"},
    }


def register_agent(client, headers, server_id):
    reg = client.post(f"/api/servers/{server_id}/registration-token", headers=headers)
    assert reg.status_code == 201, reg.text
    token = reg.json()["registration_token"]
    # Plaintext shown once; the stored record must not contain it.
    again = client.get("/api/agents", headers=headers).json()
    assert all(token not in str(a) for a in again)
    resp = client.post("/api/agent/register",
                       json={"registration_token": token, "agent_version": "1.0.0"})
    assert resp.status_code == 201, resp.text
    return resp.json()["agent_token"]


def test_health_and_auth(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/servers").status_code == 401
    bad = client.post("/api/auth/login", json={"username": "testadmin", "password": "wrong"})
    assert bad.status_code == 401
    headers = auth_headers(client)
    assert client.get("/api/auth/me", headers=headers).json()["username"] == "testadmin"


def test_server_crud_and_groups(client):
    headers = auth_headers(client)
    grp = client.post("/api/groups", headers=headers, json={"name": "Production"}).json()
    assert client.post("/api/groups", headers=headers, json={"name": "Production"}).status_code == 409
    server = make_server(client, headers, group_id=grp["id"])
    assert server["health"] in ("offline", "unknown")
    found = client.get("/api/servers", headers=headers, params={"q": "web"}).json()
    assert found["total"] == 1
    fav = client.patch(f"/api/servers/{server['id']}/favorite", headers=headers).json()
    assert fav["is_favorite"] is True
    # Group with servers cannot be deleted.
    assert client.delete(f"/api/groups/{grp['id']}", headers=headers).status_code == 409
    assert client.delete(f"/api/servers/{server['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/groups/{grp['id']}", headers=headers).status_code == 204


def test_agent_registration_and_ingest(client):
    headers = auth_headers(client)
    server = make_server(client, headers)
    agent_token = register_agent(client, headers, server["id"])
    aheaders = {"Authorization": f"Bearer {agent_token}"}
    # Bogus token rejected.
    bad = client.post("/api/agent/metrics", json=sample_report(),
                      headers={"Authorization": "Bearer bogus"})
    assert bad.status_code == 401
    first = client.post("/api/agent/metrics", json=sample_report(), headers=aheaders)
    assert first.status_code == 200, first.text
    assert first.json()["samples"] > 10
    # Second report derives throughput from counter deltas.
    second_report = sample_report()
    second_report["network"][0]["rx_bytes"] = 4600
    second_report["network"][0]["tx_bytes"] = 5600
    second_report["collected_at"] = "2026-01-01T00:01:00Z"
    second = client.post("/api/agent/metrics", json=second_report, headers=aheaders)
    assert second.status_code == 200
    detail = client.get(f"/api/servers/{server['id']}", headers=headers).json()
    assert detail["os_name"] == "Linux"
    assert detail["health"] == "healthy"
    assert detail["cpu_pct"] == 12.5
    series = client.get("/api/metrics/series", headers=headers, params={
        "server_id": server["id"], "kind": "net", "name": "eth0/rx_bps"}).json()
    assert len(series["points"]) == 1
    assert series["points"][0]["value"] == 60.0  # (4600-1000)/60s
    # Heartbeat accepted.
    hb = client.post("/api/agent/heartbeat", json={"agent_version": "1.0.1"}, headers=aheaders)
    assert hb.status_code == 200


def test_agent_token_single_use_and_revocation(client):
    headers = auth_headers(client)
    server = make_server(client, headers, name="db-1")
    reg = client.post(f"/api/servers/{server['id']}/registration-token", headers=headers).json()
    token = reg["registration_token"]
    first = client.post("/api/agent/register",
                        json={"registration_token": token, "agent_version": "1.0.0"})
    assert first.status_code == 201
    reuse = client.post("/api/agent/register",
                        json={"registration_token": token, "agent_version": "1.0.0"})
    assert reuse.status_code == 401
    agent_token = first.json()["agent_token"]
    agents = client.get("/api/agents", headers=headers).json()
    assert len(agents) == 1
    assert agents[0]["token_prefix"] == agent_token[:8]
    assert "agent_token" not in str(agents)
    assert client.delete(f"/api/agents/{agents[0]['id']}", headers=headers).status_code == 204
    used = client.post("/api/agent/metrics", json=sample_report(),
                       headers={"Authorization": f"Bearer {agent_token}"})
    assert used.status_code == 401


def test_offline_detection_and_resolution(client):
    from datetime import datetime, timedelta, timezone

    headers = auth_headers(client)
    server = make_server(client, headers, name="lonely")
    agent_token = register_agent(client, headers, server["id"])
    aheaders = {"Authorization": f"Bearer {agent_token}"}
    client.post("/api/agent/metrics", json=sample_report(), headers=aheaders)
    # Force the heartbeat stale directly, then evaluate.
    from app import database as db_module

    db = db_module.SessionLocal()
    try:
        from app.models import Agent

        agent = db.query(Agent).filter(Agent.server_id == server["id"]).first()
        agent.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()
    finally:
        db.close()
    summary = client.get("/api/dashboard/summary", headers=headers).json()
    assert summary["offline"] >= 1
    evaluated = client.post("/api/alerts/evaluate", headers=headers).json()
    assert evaluated["servers_checked"] >= 1
    offline_alerts = client.get("/api/alerts", headers=headers, params={"status": "active"}).json()
    assert any(a["alert_type"] == "offline" for a in offline_alerts["items"])
    # A new heartbeat resolves the offline incident.
    client.post("/api/agent/heartbeat", json={}, headers=aheaders)
    remaining = client.get("/api/alerts", headers=headers, params={"status": "active"}).json()
    assert not any(a["alert_type"] == "offline" for a in remaining["items"])
