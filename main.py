"""Shopify order report generator (CLI)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import load_config
from report_service import generate_report
from shopify_auth import ShopifyAuthError


def setup_logging(logs_dir: Path, level: str) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.info("Logging to %s", log_file)


def main() -> int:
    try:
        config = load_config()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    setup_logging(config.report.logs_dir, config.report.log_level)
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting report %s to %s",
        config.report.start_date,
        config.report.end_date,
    )

    try:
        result = generate_report(
            config.report.start_date,
            config.report.end_date,
        )
        print(f"Report saved: {result.file_path}")
        return 0
    except ShopifyAuthError as exc:
        logger.error("Shopify authentication failed: %s", exc)
        print(f"Authentication error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("Report failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
