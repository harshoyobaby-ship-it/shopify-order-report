"""Streamlit web UI for Shopify order reports."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

from report_service import ReportResult, generate_report
from shopify_auth import ShopifyAuthError

load_dotenv()

st.set_page_config(
    page_title="Shopify Order Report",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

logger = logging.getLogger(__name__)

BLUE_PRIMARY = "#2563EB"
BLUE_DARK = "#1E40AF"
BLUE_LIGHT = "#DBEAFE"
BLUE_BG = "#EFF6FF"


def _inject_styles() -> None:
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            html, body, [class*="css"] {{
                font-family: 'Inter', sans-serif;
            }}

            .main-header {{
                background: linear-gradient(135deg, {BLUE_DARK} 0%, {BLUE_PRIMARY} 100%);
                padding: 1.75rem 2rem;
                border-radius: 16px;
                margin-bottom: 1.5rem;
                color: white;
                box-shadow: 0 10px 40px rgba(37, 99, 235, 0.25);
            }}
            .main-header h1 {{
                color: white !important;
                font-size: 1.85rem;
                font-weight: 700;
                margin: 0;
            }}
            .main-header p {{
                color: rgba(255,255,255,0.9);
                margin: 0.35rem 0 0 0;
                font-size: 0.95rem;
            }}

            .info-card {{
                background: white;
                border: 1px solid {BLUE_LIGHT};
                border-left: 4px solid {BLUE_PRIMARY};
                border-radius: 12px;
                padding: 1rem 1.25rem;
                margin-bottom: 1rem;
            }}

            div[data-testid="stMetric"] {{
                background: white;
                border: 1px solid {BLUE_LIGHT};
                border-radius: 12px;
                padding: 0.75rem 1rem;
                box-shadow: 0 2px 8px rgba(37, 99, 235, 0.06);
            }}
            div[data-testid="stMetric"] label {{
                color: #64748B !important;
            }}
            div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
                color: {BLUE_DARK} !important;
            }}

            .stButton > button[kind="primary"] {{
                background: linear-gradient(135deg, {BLUE_PRIMARY} 0%, {BLUE_DARK} 100%);
                border: none;
                border-radius: 10px;
                font-weight: 600;
                padding: 0.65rem 1.25rem;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }}
            .stButton > button[kind="primary"]:hover {{
                transform: translateY(-1px);
                box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35);
            }}

            .stDownloadButton > button {{
                background: {BLUE_BG} !important;
                color: {BLUE_DARK} !important;
                border: 2px solid {BLUE_PRIMARY} !important;
                border-radius: 10px;
                font-weight: 600;
            }}

            div[data-testid="stSidebar"] {{
                background: linear-gradient(180deg, #F8FAFC 0%, {BLUE_BG} 100%);
            }}

            .preset-label {{
                font-size: 0.8rem;
                color: #64748B;
                font-weight: 500;
                margin-bottom: 0.5rem;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _app_password() -> str | None:
    try:
        return st.secrets.get("APP_PASSWORD") or os.getenv("APP_PASSWORD")
    except Exception:
        return os.getenv("APP_PASSWORD")


def _header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="main-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _init_session_dates() -> None:
    today = date.today()
    if "start_date" not in st.session_state:
        st.session_state.start_date = today.replace(day=1)
    if "end_date" not in st.session_state:
        st.session_state.end_date = today


def _apply_preset(label: str) -> None:
    today = date.today()
    presets: dict[str, tuple[date, date]] = {
        "Today": (today, today),
        "Last 7 days": (today - timedelta(days=6), today),
        "This month": (today.replace(day=1), today),
        "Last month": (
            (today.replace(day=1) - timedelta(days=1)).replace(day=1),
            today.replace(day=1) - timedelta(days=1),
        ),
        "Last 30 days": (today - timedelta(days=29), today),
    }
    if label in presets:
        st.session_state.start_date, st.session_state.end_date = presets[label]
        st.session_state.last_preset = label


def _render_auth() -> bool:
    password = _app_password()
    if not password:
        return True

    if st.session_state.get("authenticated"):
        return True

    _inject_styles()
    _header("Shopify Order Report", "Sign in to access your store reports")

    with st.container(border=True):
        entered = st.text_input("Password", type="password", placeholder="Enter team password")
        if st.button("Sign in", type="primary", use_container_width=True):
            if entered == password:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")
    return False


def _render_sidebar(store: str) -> None:
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        st.markdown(f"**Store**  \n`{store}`")
        st.divider()

        if _app_password():
            if st.button("Sign out", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        st.markdown("##### About the report")
        st.markdown(
            """
            - One row per **line item**
            - Orders, tax, customer & shipping
            - Fulfillment & tracking from Shopify
            """
        )

        st.divider()
        st.caption("Tip: Use presets for quick date ranges, then generate.")


def _render_presets() -> None:
    st.markdown('<p class="preset-label">Quick date ranges</p>', unsafe_allow_html=True)
    labels = ["Today", "Last 7 days", "This month", "Last month", "Last 30 days"]
    cols = st.columns(len(labels))
    for col, label in zip(cols, labels):
        with col:
            if st.button(
                label,
                use_container_width=True,
                type="secondary" if st.session_state.get("last_preset") != label else "primary",
            ):
                _apply_preset(label)
                st.rerun()


def _render_date_pickers() -> tuple[date, date]:
    _init_session_dates()
    today = date.today()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.date_input("Start date", max_value=today, key="start_date")
    with col2:
        st.date_input("End date", max_value=today, key="end_date")
    with col3:
        days = (st.session_state.end_date - st.session_state.start_date).days + 1
        st.metric("Range", f"{days} day{'s' if days != 1 else ''}")

    return st.session_state.start_date, st.session_state.end_date


def _show_result(result: ReportResult) -> None:
    st.session_state.last_report = result

    st.success("Report ready — download your Excel file below.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Orders", f"{result.order_count:,}")
    m2.metric("Line items", f"{result.row_count:,}")
    m3.metric("Issues logged", result.error_count)
    m4.metric("Generated in", f"{result.elapsed_seconds:.0f}s")

    st.download_button(
        label="⬇️ Download Excel report",
        data=result.file_bytes,
        file_name=result.filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
        key="download_report",
    )


def main() -> None:
    if not _render_auth():
        return

    _inject_styles()
    store = _store_label()
    _render_sidebar(store)

    _header(
        "Shopify Order Report",
        f"Generate and download order exports for {store}",
    )

    with st.container(border=True):
        _render_presets()
        st.divider()
        start_date, end_date = _render_date_pickers()

    if start_date > end_date:
        st.error("Start date must be on or before end date.")
        return

    range_days = (end_date - start_date).days + 1
    if range_days > 62:
        st.warning(
            f"**{range_days} days** selected — large exports may take several minutes. "
            "Try a shorter range if the request times out."
        )

    st.markdown(
        f"""
        <div class="info-card">
            <strong>What’s included:</strong> order & line-item details, GST breakdown,
            customer & shipping fields, and fulfillment tracking — exported as
            <code>shopify_orders_{start_date}_to_{end_date}.xlsx</code>
        </div>
        """,
        unsafe_allow_html=True,
    )

    gen_col, clear_col = st.columns([3, 1])
    with gen_col:
        generate_clicked = st.button(
            "🚀 Generate report",
            type="primary",
            use_container_width=True,
        )
    with clear_col:
        if st.button("Reset", use_container_width=True):
            for key in ("last_report", "last_preset"):
                st.session_state.pop(key, None)
            _init_session_dates()
            st.rerun()

    if generate_clicked:
        progress = st.progress(0, text="Starting…")
        try:
            progress.progress(15, text="Authenticating with Shopify…")
            result = generate_report(start_date, end_date, save_to_disk=False)
            progress.progress(85, text="Building Excel workbook…")
            progress.progress(100, text="Complete!")
            progress.empty()
            _show_result(result)
            st.balloons()
        except ShopifyAuthError as exc:
            progress.empty()
            st.error(f"Shopify authentication failed: {exc}")
        except ValueError as exc:
            progress.empty()
            st.error(str(exc))
        except Exception as exc:
            progress.empty()
            logger.exception("Report failed")
            st.error(f"Report failed: {exc}")

    elif "last_report" in st.session_state:
        st.markdown("##### Previous result")
        _show_result(st.session_state.last_report)


def _store_label() -> str:
    return os.getenv("SHOPIFY_SHOP_DOMAIN", "").strip() or "your store"


if __name__ == "__main__":
    main()
