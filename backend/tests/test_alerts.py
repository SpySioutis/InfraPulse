"""Alert rule evaluation tests: firing, deduplication, cooldown, resolution."""

from test_api import auth_headers, make_server, register_agent, sample_report


def test_threshold_alert_fires_and_resolves(client):
    headers = auth_headers(client)
    server = make_server(client, headers)
    agent_token = register_agent(client, headers, server["id"])
    aheaders = {"Authorization": f"Bearer {agent_token}"}
    rule = client.post("/api/alert-rules", headers=headers, json={
        "name": "high cpu", "server_id": server["id"], "metric": "cpu_total",
        "operator": ">", "threshold": 80, "severity": "critical",
        "cooldown_minutes": 60}).json()
    assert rule["id"]

    hot = sample_report()
    hot["cpu"]["total_pct"] = 95.0
    hot["collected_at"] = "2026-01-01T00:01:00Z"
    client.post("/api/agent/metrics", json=hot, headers=aheaders)
    active = client.get("/api/alerts", headers=headers, params={"status": "active"}).json()
    assert len(active["items"]) == 1
    assert active["items"][0]["severity"] == "critical"
    assert active["items"][0]["metric_value"] == 95.0
    # Notifications are created in-app.
    notes = client.get("/api/notifications", headers=headers).json()
    assert any("high cpu" in n["title"] or "cpu" in n["body"] for n in notes)

    # Re-ingesting the breach does not duplicate the incident.
    hot2 = sample_report()
    hot2["cpu"]["total_pct"] = 95.0
    hot2["collected_at"] = "2026-01-01T00:02:00Z"
    client.post("/api/agent/metrics", json=hot2, headers=aheaders)
    active2 = client.get("/api/alerts", headers=headers, params={"status": "active"}).json()
    assert len(active2["items"]) == 1

    # Acknowledge, then clear the breach: the alert resolves.
    ack = client.post(f"/api/alerts/{active['items'][0]['id']}/acknowledge", headers=headers)
    assert ack.json()["status"] == "acknowledged"
    cool = sample_report()
    cool["cpu"]["total_pct"] = 10.0
    cool["collected_at"] = "2026-01-01T00:03:00Z"
    cool_resp = client.post("/api/agent/metrics", json=cool, headers=aheaders)
    assert cool_resp.status_code == 200, cool_resp.text
    remaining = client.get("/api/alerts", headers=headers, params={"status": "active"}).json()
    assert remaining["total"] == 0
    resolved = client.get("/api/alerts", headers=headers, params={"status": "resolved"}).json()
    assert resolved["total"] == 1

    # Manual resolve endpoint also works.
    assert client.post(f"/api/alerts/{resolved['items'][0]['id']}/resolve", headers=headers).status_code == 200


def test_rule_validation_and_management(client):
    headers = auth_headers(client)
    server = make_server(client, headers)
    bad_metric = client.post("/api/alert-rules", headers=headers, json={
        "name": "x", "server_id": server["id"], "metric": "nonsense", "operator": ">", "threshold": 1})
    assert bad_metric.status_code == 400
    bad_server = client.post("/api/alert-rules", headers=headers, json={
        "name": "x", "server_id": "missing", "metric": "cpu_total", "operator": ">", "threshold": 1})
    assert bad_server.status_code == 404
    rule = client.post("/api/alert-rules", headers=headers, json={
        "name": "mem watch", "metric": "memory_used_pct",
        "operator": ">=", "threshold": 90, "severity": "warning"}).json()
    assert rule["severity"] == "warning"
    updated = client.put(f"/api/alert-rules/{rule['id']}", headers=headers, json={
        "name": "mem watch", "metric": "memory_used_pct",
        "operator": ">=", "threshold": 95, "severity": "warning"}).json()
    assert updated["threshold"] == 95
    assert client.delete(f"/api/alert-rules/{rule['id']}", headers=headers).status_code == 204
