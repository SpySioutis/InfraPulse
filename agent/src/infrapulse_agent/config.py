"""Agent configuration: JSON file plus environment overrides.

Resolution order: explicit argument > environment variable > config file
> built-in default. The agent token is written back to the config file
on registration (mode 0600, best effort).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

AGENT_VERSION = "1.0.0"
DEFAULT_CONFIG_PATH = "/etc/infrapulse/agent.json"


class AgentConfig:
    def __init__(
        self,
        server_url: str = "http://localhost:8003",
        registration_token: str = "",
        agent_token: str = "",
        interval_seconds: int = 60,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.registration_token = registration_token
        self.agent_token = agent_token
        self.interval_seconds = interval_seconds

    @classmethod
    def load(cls, path: str | None = None) -> AgentConfig:
        config_path = path or os.environ.get("AGENT_CONFIG", DEFAULT_CONFIG_PATH)
        data: dict = {}
        try:
            data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return cls(
            server_url=os.environ.get("SERVER_URL", data.get("server_url", "http://localhost:8003")),
            registration_token=os.environ.get(
                "REGISTRATION_TOKEN", data.get("registration_token", "")),
            agent_token=os.environ.get("AGENT_TOKEN", data.get("agent_token", "")),
            interval_seconds=int(
                os.environ.get("AGENT_INTERVAL_SECONDS", data.get("interval_seconds", 60))),
        )

    def save_token(self, path: str | None, token: str) -> None:
        config_path = path or os.environ.get("AGENT_CONFIG", DEFAULT_CONFIG_PATH)
        data: dict = {}
        try:
            data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data["agent_token"] = token
        data.pop("registration_token", None)  # single-use: never persist it
        target = Path(config_path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass
        except OSError as exc:
            raise RuntimeError(f"Cannot write agent config to {config_path}: {exc}") from exc
        self.agent_token = token
        self.registration_token = ""
