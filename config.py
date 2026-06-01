"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key, default)
    return value.strip() if value else None


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ShopifyConfig:
    shop_domain: str
    client_id: str | None
    client_secret: str | None
    access_token: str | None
    api_version: str
    requests_per_second: float
    max_retries: int
    timeout_seconds: int
    backoff_multiplier: float
    min_wait_seconds: float
    max_wait_seconds: float

    @property
    def base_url(self) -> str:
        domain = self.shop_domain.replace("https://", "").replace("http://", "")
        if not domain.endswith(".myshopify.com"):
            domain = f"{domain}.myshopify.com"
        return f"https://{domain}/admin/api/{self.api_version}"


@dataclass(frozen=True)
class ReportConfig:
    start_date: str
    end_date: str
    max_orders: int
    reports_dir: Path
    logs_dir: Path
    log_level: str
    output_filename: str = "shopify_orders.xlsx"


@dataclass(frozen=True)
class AppConfig:
    shopify: ShopifyConfig
    report: ReportConfig


def load_config(
    start_date: str | None = None,
    end_date: str | None = None,
) -> AppConfig:
    shop_domain = _env("SHOPIFY_SHOP_DOMAIN")
    client_id = _env("SHOPIFY_CLIENT_ID")
    client_secret = _env("SHOPIFY_CLIENT_SECRET")
    access_token = _env("SHOPIFY_ACCESS_TOKEN")

    if not shop_domain:
        raise ValueError("SHOPIFY_SHOP_DOMAIN is required.")

    if not access_token and (not client_id or not client_secret):
        raise ValueError(
            "Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET, or SHOPIFY_ACCESS_TOKEN. "
            "Copy .env.example to .env and fill in values."
        )

    resolved_start = start_date or _env("REPORT_START_DATE")
    resolved_end = end_date or _env("REPORT_END_DATE")
    if not resolved_start or not resolved_end:
        raise ValueError(
            "Report dates are required (pass start_date/end_date or set "
            "REPORT_START_DATE and REPORT_END_DATE in .env)."
        )

    reports_dir = BASE_DIR / _env("REPORTS_DIR", "reports")
    logs_dir = BASE_DIR / _env("LOGS_DIR", "logs")
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    shopify = ShopifyConfig(
        shop_domain=shop_domain,
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        api_version=_env("SHOPIFY_API_VERSION", "2024-10") or "2024-10",
        requests_per_second=_env_float("SHOPIFY_REQUESTS_PER_SECOND", 2.0),
        max_retries=_env_int("MAX_RETRIES", 5),
        timeout_seconds=_env_int("REQUEST_TIMEOUT_SECONDS", 60),
        backoff_multiplier=_env_float("RETRY_BACKOFF_MULTIPLIER", 2.0),
        min_wait_seconds=_env_float("RETRY_MIN_WAIT_SECONDS", 1.0),
        max_wait_seconds=_env_float("RETRY_MAX_WAIT_SECONDS", 60.0),
    )

    report = ReportConfig(
        start_date=resolved_start,
        end_date=resolved_end,
        max_orders=_env_int("MAX_ORDERS", 0),
        reports_dir=reports_dir,
        logs_dir=logs_dir,
        log_level=_env("LOG_LEVEL", "INFO") or "INFO",
    )

    return AppConfig(shopify=shopify, report=report)
