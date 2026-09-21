"""
Observability dashboard for the AIOps Copilot MCP server.

Reads exclusively from the `tool_calls` table — every number on this page
comes from real logged calls (see mcp_server/logging_middleware.py). If no
calls have been logged yet, the charts are simply empty; nothing here is
synthesized to make the page look populated.
"""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text

from db.models import get_engine

load_dotenv()

st.set_page_config(page_title="AIOps Copilot — Observability", layout="wide")

REFRESH_SECONDS = int(os.environ.get("DASHBOARD_REFRESH_SECONDS", "10"))


def _load_tool_calls() -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT * FROM tool_calls ORDER BY created_at"), conn)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


@st.fragment(run_every=REFRESH_SECONDS)
def render_dashboard() -> None:
    df = _load_tool_calls()

    st.title("AIOps Copilot — Observability")
    st.caption(f"Reading live from `tool_calls` · auto-refreshing every {REFRESH_SECONDS}s")

    if df.empty:
        st.info("No tool calls logged yet. Call a tool through the MCP server to see data here.")
        return

    total_calls = len(df)
    error_count = int((df["status"] == "error").sum())
    error_rate = error_count / total_calls if total_calls else 0.0
    total_cost = float(df["cost_usd"].sum())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total calls", total_calls)
    col2.metric("Error rate", f"{error_rate:.1%}")
    col3.metric("Cumulative cost (USD)", f"${total_cost:.6f}")
    col4.metric("Distinct callers", df["caller_id"].nunique())

    st.subheader("Calls per tool over time")
    df_time = df.set_index("created_at")
    calls_per_bucket = (
        df_time.groupby([pd.Grouper(freq="5min"), "tool_name"])
        .size()
        .rename("calls")
        .reset_index()
        .pivot(index="created_at", columns="tool_name", values="calls")
        .fillna(0)
    )
    st.bar_chart(calls_per_bucket)

    st.subheader("Latency per tool (p50 / p95, ms)")
    latency_stats = (
        df.groupby("tool_name")["latency_ms"]
        .agg(p50=lambda s: s.quantile(0.5), p95=lambda s: s.quantile(0.95), calls="count")
        .round(1)
    )
    st.dataframe(latency_stats, use_container_width=True)

    st.subheader("Error rate per tool")
    error_by_tool = (
        df.groupby("tool_name")["status"]
        .apply(lambda s: (s == "error").mean())
        .rename("error_rate")
        .to_frame()
    )
    error_by_tool["error_rate"] = (error_by_tool["error_rate"] * 100).round(1)
    st.dataframe(error_by_tool, use_container_width=True)

    st.subheader("Cumulative cost over time")
    cost_over_time = df_time["cost_usd"].cumsum()
    st.line_chart(cost_over_time)

    with st.expander("Raw tool_calls (most recent 200)"):
        st.dataframe(df.sort_values("created_at", ascending=False).head(200), use_container_width=True)


render_dashboard()
