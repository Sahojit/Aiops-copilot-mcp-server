"""
Instrumentation wrapper for MCP tools: runs auth + rate-limit checks, times
the call, and writes one row to `tool_calls` per invocation — success or
failure. This is what stitches auth.py and rate_limit.py into every tool.

Convention: the wrapped implementation function receives `(ctx, caller,
**kwargs)` and returns a JSON-serializable dict. If that dict has an
`expected_cost_usd` key (only true for recommend_model_route), it's logged
as cost_usd; every other tool logs 0.0, matching the brief.
"""
import functools
import json
import time
from typing import Any, Callable

from mcp.server.mcpserver import Context
from mcp.shared.exceptions import MCPError

from db.models import ToolCall, get_session_factory
from mcp_server import auth, rate_limit

_SessionFactory = get_session_factory()


def _log_call(
    *,
    tool_name: str,
    caller_id: str,
    args: dict[str, Any],
    result_summary: str,
    latency_ms: float,
    cost_usd: float,
    status: str,
) -> None:
    session = _SessionFactory()
    try:
        session.add(
            ToolCall(
                tool_name=tool_name,
                caller_id=caller_id,
                args=args,
                result_summary=result_summary[:500],
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                status=status,
            )
        )
        session.commit()
    finally:
        session.close()


def instrumented_tool(tool_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ctx: Context, **kwargs: Any) -> Any:
            start = time.perf_counter()
            caller_id = "unknown"
            status = "success"
            result_summary = ""
            cost_usd = 0.0
            result: Any = None

            try:
                caller = auth.authenticate(ctx)
                caller_id = caller.caller_id
                rate_limit.rate_limiter.check(caller_id)
                result = await func(ctx, caller, **kwargs)
                result_summary = json.dumps(result)[:500]
                if isinstance(result, dict) and "expected_cost_usd" in result:
                    cost_usd = float(result["expected_cost_usd"])
                return result
            except MCPError as e:
                status = "error"
                result_summary = e.message
                raise
            except Exception as e:  # noqa: BLE001 — logged then re-raised, not swallowed
                status = "error"
                result_summary = str(e)
                raise
            finally:
                latency_ms = (time.perf_counter() - start) * 1000
                _log_call(
                    tool_name=tool_name,
                    caller_id=caller_id,
                    args=kwargs,
                    result_summary=result_summary,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                    status=status,
                )

        return wrapper

    return decorator
