"""Export consolidated report to Excel with formatting."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from data_mapper import OUTPUT_COLUMNS

logger = logging.getLogger(__name__)

DATE_COLUMNS = {
    "Order Date",
    "Dispatch Date",
    "Delivery Date",
    "Created At",
    "Updated At",
}


class ExcelExporter:
    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path

    def export(
        self,
        rows: list[dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> Path:
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.export_bytes(rows, errors)
        self._output_path.write_bytes(data)
        logger.info("Wrote report to %s (%s rows)", self._output_path, len(rows))
        return self._output_path

    def export_bytes(
        self,
        rows: list[dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> bytes:
        buffer = io.BytesIO()
        df, errors_df = self._prepare_frames(rows, errors)

        with pd.ExcelWriter(
            buffer,
            engine="openpyxl",
            datetime_format="yyyy-mm-dd hh:mm:ss",
        ) as writer:
            df.to_excel(writer, sheet_name="Orders", index=False)
            errors_df.to_excel(writer, sheet_name="Error Log", index=False)

            orders_sheet = writer.sheets["Orders"]
            self._format_sheet(orders_sheet, df)
            if not errors_df.empty:
                self._format_sheet(writer.sheets["Error Log"], errors_df, freeze=False)

        return buffer.getvalue()

    @staticmethod
    def _prepare_frames(
        rows: list[dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
        errors_df = (
            pd.DataFrame(errors)
            if errors
            else pd.DataFrame(columns=["order_id", "order_number", "error"])
        )

        for col in DATE_COLUMNS:
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce", utc=True)
                df[col] = (
                    parsed.dt.tz_localize(None)
                    if parsed.dt.tz is None
                    else parsed.dt.tz_convert("UTC").dt.tz_localize(None)
                )

        return df, errors_df

    @staticmethod
    def _format_sheet(sheet: Any, df: pd.DataFrame, freeze: bool = True) -> None:
        header_font = Font(bold=True)
        for cell in sheet[1]:
            cell.font = header_font

        for idx, column in enumerate(df.columns, start=1):
            letter = get_column_letter(idx)
            max_len = len(str(column))
            series = df[column].astype(str)
            if len(series) > 0:
                max_len = max(max_len, series.str.len().max())
            sheet.column_dimensions[letter].width = min(max_len + 2, 50)

            if column in DATE_COLUMNS:
                for row in range(2, len(df) + 2):
                    cell = sheet[f"{letter}{row}"]
                    cell.number_format = "yyyy-mm-dd hh:mm:ss"

        if freeze and len(df) > 0:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
