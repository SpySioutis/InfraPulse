"""Agent unit tests: collector shape, config handling, client logic (mocked HTTP)."""

import json
from unittest.mock import patch

import pytest

from infrapulse_agent import collect as collect_module
from infrapulse_agent.client import AgentError, AuthError, register
from infrapulse_agent.config import AgentConfig


def test_collector_report_shape():
    report = collect_module.Collector().collect()
    assert set(report) == {"agent_version", "collected_at", "cpu", "memory", "disks", "network", "system"}
    assert report["cpu"]["count"] >= 1
    assert 0 <= report["cpu"]["total_pct"] <= 100
    assert report["memory"]["total_bytes"] > 0
    assert report["memory"]["used_pct"] >= 0
    assert isinstance(report["disks"], list)
    assert isinstance(report["network"], list)
    assert report["system"]["uptime_seconds"] >= 0


def test_collector_survives_psutil_errors(monkeypatch):
    monkeypatch.setattr(collect_module.psutil, "cpu_percent", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
    monkeypatch.setattr(collect_module.psutil, "cpu_count", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
    report = collect_module.Collector().collect()
    assert report["cpu"]["total_pct"] == 0.0
    assert report["cpu"]["count"] == 1


def test_config_env_overrides_file(tmp_path, monkeypatch):
    cfg_file = tmp_path / "agent.json"
    cfg_file.write_text(json.dumps({"server_url": "http://file:8000", "interval_seconds": 60}))
    monkeypatch.setenv("SERVER_URL", "http://env:9000")
    monkeypatch.delenv("REGISTRATION_TOKEN", raising=False)
    cfg = AgentConfig.load(str(cfg_file))
    assert cfg.server_url == "http://env:9000"
    assert cfg.interval_seconds == 60


def test_config_save_token_drops_registration_token(tmp_path):
    cfg_file = tmp_path / "agent.json"
    cfg = AgentConfig.load(str(cfg_file))
    cfg.save_token(str(cfg_file), "ipa_secret")
    saved = json.loads(cfg_file.read_text())
    assert saved["agent_token"] == "ipa_secret"
    assert "registration_token" not in saved
    assert cfg.registration_token == ""


def test_register_requires_token():
    with pytest.raises(AgentError):
        register(AgentConfig(server_url="http://x", registration_token=""))


def test_agent_rejects_revoked_token_surfaces_auth_error(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(urllib_request_module(), "urlopen", fake_urlopen)
    from infrapulse_agent import client as client_module

    cfg = AgentConfig(server_url="http://x", agent_token="ipa_dead")
    with pytest.raises(AuthError):
        client_module.send_heartbeat(cfg)


def urllib_request_module():
    import urllib.request

    return urllib.request
