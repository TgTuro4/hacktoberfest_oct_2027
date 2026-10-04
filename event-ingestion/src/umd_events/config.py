"""Runtime configuration, loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

TIMEZONE = ZoneInfo("America/New_York")

# McKeldin Mall, used as the "center of campus" for distance calculations.
UMD_CENTER = (38.98599, -76.94227)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    return int(value) if value is not None else default


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    return float(value) if value is not None else default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(PROJECT_ROOT / "data"))))

    user_agent: str = field(
        default_factory=lambda: _env(
            "USER_AGENT",
            "UMDEventAggregator/1.0 (student hackathon project; event discovery for UMD)",
        )
    )
    # Minimum delay between two uncached requests to the same host.
    request_interval_s: float = field(default_factory=lambda: _env_float("REQUEST_INTERVAL_S", 0.5))
    request_timeout_s: float = field(default_factory=lambda: _env_float("REQUEST_TIMEOUT_S", 30))
    # Default HTTP cache lifetime. Listing endpoints are polled at most this often.
    cache_ttl_s: int = field(default_factory=lambda: _env_int("HTTP_CACHE_TTL_S", 30 * 60))
    # Event detail pages change rarely, so they are cached longer.
    detail_cache_ttl_s: int = field(default_factory=lambda: _env_int("DETAIL_CACHE_TTL_S", 7 * 24 * 3600))
    # Parallel requests for detail pages (each still spaced by request_interval_s).
    detail_workers: int = field(default_factory=lambda: _env_int("DETAIL_WORKERS", 3))

    # How far ahead to collect events.
    horizon_days: int = field(default_factory=lambda: _env_int("HORIZON_DAYS", 90))
    # Source events not seen for this long are treated as removed upstream.
    stale_after_days: int = field(default_factory=lambda: _env_int("STALE_AFTER_DAYS", 3))

    umd_calendar_fetch_details: bool = field(
        default_factory=lambda: _env_bool("UMD_CALENDAR_FETCH_DETAILS", True)
    )
    umd_calendar_token: str | None = field(default_factory=lambda: _env("UMD_CALENDAR_GRAPHQL_TOKEN"))
    # Uncached calendar pages take ~8s for the site to render, so enrich progressively: at most this many
    # new detail pages per run, only for in-person events in the next N days. Later runs fill in the rest.
    umd_calendar_max_detail_fetches: int = field(
        default_factory=lambda: _env_int("UMD_CALENDAR_MAX_DETAIL_FETCHES", 150)
    )
    umd_calendar_detail_days: int = field(default_factory=lambda: _env_int("UMD_CALENDAR_DETAIL_DAYS", 60))

    ticketmaster_api_key: str | None = field(default_factory=lambda: _env("TICKETMASTER_API_KEY"))
    ticketmaster_radius_miles: int = field(default_factory=lambda: _env_int("TICKETMASTER_RADIUS_MILES", 10))

    # Geocoding of addresses that are not in the local venue table (OpenStreetMap Nominatim).
    geocoder: str = field(default_factory=lambda: _env("GEOCODER", "nominatim"))
    geocode_max_per_run: int = field(default_factory=lambda: _env_int("GEOCODE_MAX_PER_RUN", 60))

    # Optional local LLM tagging through Ollama (free, open-source models).
    llm_tagging: bool = field(default_factory=lambda: _env_bool("LLM_TAGGING", False))
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5:3b"))
    llm_max_events_per_run: int = field(default_factory=lambda: _env_int("LLM_MAX_EVENTS_PER_RUN", 200))

    api_cors_origins: list[str] = field(
        default_factory=lambda: (_env("API_CORS_ORIGINS", "*") or "*").split(",")
    )

    @property
    def db_path(self) -> Path:
        return Path(_env("DB_PATH", str(self.data_dir / "events.duckdb")))

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def export_dir(self) -> Path:
        return Path(_env("EXPORT_DIR", str(self.data_dir / "exports")))

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.cache_dir, self.export_dir):
            path.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
