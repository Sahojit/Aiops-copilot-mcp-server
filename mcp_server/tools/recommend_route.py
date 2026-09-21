"""
recommend_model_route — calls the (mocked) Model Arbitration Engine with a
task description and latency/cost budgets, returns the chosen model and a
simulated expected cost. This is the one tool that logs a nonzero cost_usd
to tool_calls, matching the brief.
"""
import os
from typing import Any

import httpx
from mcp.server.mcpserver import Context

from mcp_server.auth import Caller
from mcp_server.logging_middleware import instrumented_tool

ARBITRATION_SERVICE_URL = os.environ.get("ARBITRATION_SERVICE_URL", "http://localhost:8003")


async def _recommend_model_route_impl(
    ctx: Context,
    caller: Caller,
    task_description: str,
    latency_budget_ms: int,
    cost_budget_usd: float,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{ARBITRATION_SERVICE_URL}/route",
            json={
                "task_description": task_description,
                "latency_budget_ms": latency_budget_ms,
                "cost_budget_usd": cost_budget_usd,
            },
        )
        response.raise_for_status()
        return response.json()


recommend_model_route = instrumented_tool("recommend_model_route")(_recommend_model_route_impl)
