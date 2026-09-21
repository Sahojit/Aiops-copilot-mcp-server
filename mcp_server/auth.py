"""
API-key authentication for the MCP server.

The MCP server runs over streamable-HTTP transport (not stdio), so each tool
call carries HTTP headers that `Context.headers` exposes. `authenticate()`
reads `X-API-Key` from those headers and maps it to a caller identity; tools
call it first and reject the request if it raises.

Keys are configured via the `API_KEYS_JSON` env var — a JSON object mapping
API key -> {"caller_id": str, "can_approve_mitigations": bool}. See
.env.example for the local dev keys used by claude_desktop_config.json.
"""
import json
import os
from dataclasses import dataclass

from mcp.server.mcpserver import Context
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_REQUEST


@dataclass(frozen=True)
class Caller:
    api_key: str
    caller_id: str
    can_approve_mitigations: bool


def _load_api_keys() -> dict[str, Caller]:
    raw = os.environ.get("API_KEYS_JSON")
    if not raw:
        # Local dev defaults — documented in .env.example. Not for production use.
        raw = json.dumps(
            {
                "dev-key-desktop-1": {"caller_id": "desktop-client-1", "can_approve_mitigations": False},
                "dev-key-approver": {"caller_id": "oncall-lead", "can_approve_mitigations": True},
            }
        )
    parsed = json.loads(raw)
    return {
        key: Caller(
            api_key=key,
            caller_id=value["caller_id"],
            can_approve_mitigations=bool(value.get("can_approve_mitigations", False)),
        )
        for key, value in parsed.items()
    }


_API_KEYS = _load_api_keys()


def authenticate(ctx: Context) -> Caller:
    """Validate the X-API-Key header on `ctx` and return the matching Caller.

    Raises MCPError(INVALID_REQUEST) if the header is missing or unrecognized.
    """
    headers = ctx.headers or {}
    # HTTP headers are case-insensitive; Context.headers preserves whatever
    # casing the transport handed us, so normalize before lookup.
    normalized = {k.lower(): v for k, v in headers.items()}
    api_key = normalized.get("x-api-key")

    if not api_key:
        raise MCPError(INVALID_REQUEST, "Missing X-API-Key header")

    caller = _API_KEYS.get(api_key)
    if caller is None:
        raise MCPError(INVALID_REQUEST, "Invalid API key")

    return caller
