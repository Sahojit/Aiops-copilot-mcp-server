"""
diagnose_incident — calls the (mocked) AIOps RCA service with a metrics
snapshot and returns its root-cause diagnosis. Read-only: does not write to
the incidents table, only to tool_calls (via the instrumented_tool wrapper).
"""
import os
from typing import Any

import httpx
from mcp.server.mcpserver import Context

from mcp_server.auth import Caller
from mcp_server.logging_middleware import instrumented_tool

RCA_SERVICE_URL = os.environ.get("RCA_SERVICE_URL", "http://localhost:8001")


async def _diagnose_incident_impl(
    ctx: Context,
    caller: Caller,
    service_name: str,
    metrics: dict[str, Any],
    window_minutes: int = 15,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{RCA_SERVICE_URL}/rca/diagnose",
            json={"service_name": service_name, "metrics": metrics, "window_minutes": window_minutes},
        )
        response.raise_for_status()
        return response.json()


diagnose_incident = instrumented_tool("diagnose_incident")(_diagnose_incident_impl)
