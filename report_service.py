"""Generate Shopify order reports (shared by CLI and web UI)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from config import load_config
from data_mapper import DataMapper
from excel_exporter import ExcelExporter
from shopify_client import ShopifyAPIError, ShopifyClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportResult:
    file_bytes: bytes
    filename: str
    order_count: int
    row_count: int
    error_count: int
    elapsed_seconds: float
    file_path: Path | None = None


def _filename_for_range(start_date: str, end_date: str) -> str:
    return f"shopify_orders_{start_date}_to_{end_date}.xlsx"


def generate_report(
    start_date: date | str,
    end_date: date | str,
    *,
    save_to_disk: bool = True,
) -> ReportResult:
    """Fetch Shopify orders and build an Excel workbook for the date range."""
    start = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
    end = end_date.isoformat() if isinstance(end_date, date) else str(end_date)

    if start > end:
        raise ValueError("Start date must be on or before end date.")

    config = load_config(start_date=start, end_date=end)
    shopify = ShopifyClient(config.shopify)
    mapper = DataMapper(shopify)

    all_rows: list[dict] = []
    errors: list[dict[str, str]] = []
    order_count = 0
    row_count = 0
    started = time.perf_counter()

    try:
        for order in shopify.iter_orders(start, end):
            order_count += 1
            if config.report.max_orders and order_count > config.report.max_orders:
                logger.info("Reached MAX_ORDERS limit (%s)", config.report.max_orders)
                break

            try:
                rows = mapper.map_order_to_rows(order, errors)
                all_rows.extend(rows)
                row_count += len(rows)
            except Exception as exc:
                logger.exception("Failed processing order %s", order.get("id"))
                errors.append(
                    {
                        "order_id": str(order.get("id", "")),
                        "order_number": str(order.get("order_number", "")),
                        "error": str(exc),
                    }
                )
    except ShopifyAPIError:
        logger.exception("Shopify API failure")
        raise

    filename = _filename_for_range(start, end)
    exporter = ExcelExporter(Path("_unused.xlsx"))
    file_bytes = exporter.export_bytes(all_rows, errors)

    file_path: Path | None = None
    if save_to_disk:
        file_path = config.report.reports_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(file_bytes)
        logger.info("Wrote report to %s", file_path)

    elapsed = time.perf_counter() - started
    logger.info(
        "Complete: %s orders, %s rows, %s errors, %.1fs",
        order_count,
        row_count,
        len(errors),
        elapsed,
    )

    return ReportResult(
        file_bytes=file_bytes,
        filename=filename,
        order_count=order_count,
        row_count=row_count,
        error_count=len(errors),
        elapsed_seconds=elapsed,
        file_path=file_path,
    )
