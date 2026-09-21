"""
score_recent_commits — calls the (mocked) Commit Risk Predictor for a
service + time window and returns the ranked, risk-scored commit list.
Read-only: only writes to tool_calls (via the instrumented_tool wrapper).
"""
import os
from typing import Any

import httpx
from mcp.server.mcpserver import Context

from mcp_server.auth import Caller
from mcp_server.logging_middleware import instrumented_tool

COMMIT_RISK_SERVICE_URL = os.environ.get("COMMIT_RISK_SERVICE_URL", "http://localhost:8002")


async def _score_recent_commits_impl(
    ctx: Context,
    caller: Caller,
    service_name: str,
    window_hours: int = 24,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{COMMIT_RISK_SERVICE_URL}/commits/score",
            json={"service_name": service_name, "window_hours": window_hours},
        )
        response.raise_for_status()
        return response.json()


score_recent_commits = instrumented_tool("score_recent_commits")(_score_recent_commits_impl)
