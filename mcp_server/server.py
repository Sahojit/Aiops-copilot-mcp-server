"""
AIOps Copilot MCP server.

Runs over streamable-HTTP transport (not stdio) because API-key auth is
header-based (X-API-Key) — see mcp_server/auth.py for why. Each tool call is
authenticated, rate-limited, and logged to the `tool_calls` table by the
instrumented_tool wrapper in mcp_server/logging_middleware.py.
"""
import os

from dotenv import load_dotenv
from mcp.server.mcpserver import Context, MCPServer

load_dotenv()

from mcp_server.tools.diagnose_incident import diagnose_incident
from mcp_server.tools.score_commits import score_recent_commits
from mcp_server.tools.recommend_route import recommend_model_route
from mcp_server.tools.propose_mitigation import propose_mitigation, confirm_mitigation

mcp = MCPServer(
    name="aiops-copilot",
    instructions=(
        "Tools for triaging a production incident: diagnose root cause, "
        "score recent commits for risk, and recommend a cost-aware model "
        "route. Backed by mock upstream services until the real ones are "
        "wired in."
    ),
)


@mcp.tool(name="diagnose_incident")
async def diagnose_incident_tool(
    ctx: Context,
    service_name: str,
    metrics: dict,
    window_minutes: int = 15,
) -> dict:
    """Diagnose the likely root cause of an incident from a metrics snapshot."""
    return await diagnose_incident(ctx, service_name=service_name, metrics=metrics, window_minutes=window_minutes)


@mcp.tool(name="score_recent_commits")
async def score_recent_commits_tool(
    ctx: Context,
    service_name: str,
    window_hours: int = 24,
) -> dict:
    """Rank recent commits to a service by bug-risk score."""
    return await score_recent_commits(ctx, service_name=service_name, window_hours=window_hours)


@mcp.tool(name="recommend_model_route")
async def recommend_model_route_tool(
    ctx: Context,
    task_description: str,
    latency_budget_ms: int,
    cost_budget_usd: float,
) -> dict:
    """Recommend which model to route a task to given latency and cost budgets."""
    return await recommend_model_route(
        ctx,
        task_description=task_description,
        latency_budget_ms=latency_budget_ms,
        cost_budget_usd=cost_budget_usd,
    )


@mcp.tool(name="propose_mitigation")
async def propose_mitigation_tool(ctx: Context, incident_id: int) -> dict:
    """Draft a mitigation action for an incident. Read-only except for writing the draft row — never executes anything."""
    return await propose_mitigation(ctx, incident_id=incident_id)


@mcp.tool(name="confirm_mitigation")
async def confirm_mitigation_tool(ctx: Context, draft_id: int, approved: bool) -> dict:
    """Approve or reject a drafted mitigation. Requires the caller's API key to carry can_approve_mitigations."""
    return await confirm_mitigation(ctx, draft_id=draft_id, approved=approved)


if __name__ == "__main__":
    host = os.environ.get("MCP_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_SERVER_PORT", "8080"))
    mcp.run(transport="streamable-http", host=host, port=port)
