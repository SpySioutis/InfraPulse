"""Agent HTTP client: registration, heartbeats and metric delivery.

Stdlib only (urllib): no extra runtime dependencies beyond psutil.
Retries with exponential backoff; 401 means revoked/invalid credentials
and stops retrying so logs stay actionable.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from infrapulse_agent.config import AGENT_VERSION, AgentConfig

logger = logging.getLogger("infrapulse-agent")

_TIMEOUT_SECONDS = 15


class AgentError(Exception):
    pass


class AuthError(AgentError):
    """Token invalid or revoked: re-register instead of retrying."""


def _request(config: AgentConfig, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": f"infrapulse-agent/{AGENT_VERSION}"}
    if config.agent_token:
        headers["Authorization"] = f"Bearer {config.agent_token}"
    req = urllib.request.Request(
        config.server_url + path, data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:500]
        if exc.code in (401, 403):
            raise AuthError(f"server rejected credentials ({exc.code}): {detail}") from exc
        raise AgentError(f"server error {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AgentError(f"cannot reach server: {exc}") from exc


def register(config: AgentConfig, config_path: str | None = None) -> str:
    if not config.registration_token:
        raise AgentError("No registration token configured (REGISTRATION_TOKEN or config file).")
    out = _request(
        config, "POST", "/api/agent/register",
        {"registration_token": config.registration_token, "agent_version": AGENT_VERSION},
    )
    token = out.get("agent_token", "")
    if not token:
        raise AgentError("Registration did not return an agent token.")
    config.save_token(config_path, token)
    logger.info("registered with central server; agent token stored")
    return token


def send_heartbeat(config: AgentConfig) -> dict:
    return _request(config, "POST", "/api/agent/heartbeat", {"agent_version": AGENT_VERSION})


def send_metrics(config: AgentConfig, report: dict) -> dict:
    return _request(config, "POST", "/api/agent/metrics", report)


def run_forever(config: AgentConfig, config_path: str | None = None) -> None:
    from infrapulse_agent.collect import Collector

    if not config.agent_token:
        register(config, config_path)
    collector = Collector()
    collector.prime()
    try:
        send_heartbeat(config)
    except AgentError as exc:
        logger.warning("initial heartbeat failed: %s", exc)
    backoff = 5
    while True:
        try:
            report = collector.collect()
            result = send_metrics(config, report)
            logger.info(
                "reported %d samples (alerts fired: %s)",
                result.get("samples", 0), result.get("alerts_fired", 0),
            )
            backoff = 5
            time.sleep(max(5, config.interval_seconds))
        except AuthError as exc:
            logger.error("%s -- re-register the agent, then restart", exc)
            raise SystemExit(2) from exc
        except AgentError as exc:
            logger.warning("delivery failed (%s); retrying in %ss", exc, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
        except KeyboardInterrupt:
            logger.info("stopping on user request")
            return
