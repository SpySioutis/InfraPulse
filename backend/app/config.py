"""Application configuration loaded from environment variables.

Health thresholds and retention live here (centralized, no hardcoded
spreads scattered through the codebase). Operators override via .env.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://infrapulse:infrapulse@localhost:5432/infrapulse"

    admin_username: str = ""
    admin_password: str = ""

    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expiry_minutes: int = 720

    metric_retention_days: int = 30
    heartbeat_grace_seconds: int = 180

    cpu_warn_pct: float = 75.0
    cpu_crit_pct: float = 90.0
    mem_warn_pct: float = 80.0
    mem_crit_pct: float = 95.0
    disk_warn_pct: float = 80.0
    disk_crit_pct: float = 95.0

    login_max_attempts: int = 5
    login_window_seconds: int = 60

    @field_validator(
        "jwt_expiry_minutes",
        "metric_retention_days",
        "heartbeat_grace_seconds",
        "login_max_attempts",
        "login_window_seconds",
    )
    @classmethod
    def _positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be positive")
        return value


settings = Settings()
