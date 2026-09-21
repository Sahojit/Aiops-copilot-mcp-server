"""
The gated mitigation flow: propose_mitigation drafts a plausible action and
writes it to `mitigations` with status='drafted' — it never executes
anything. confirm_mitigation is the only place an action can move to
'executed', and only for a caller whose own API key carries
can_approve_mitigations=True; that flag comes from server-side auth
(mcp_server/auth.py), never from a tool argument, so a caller cannot grant
itself approval by passing approved=True.
"""
import logging
import os
import random
from datetime import datetime
from typing import Any

from mcp.server.mcpserver import Context
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, INVALID_REQUEST

from db.models import Incident, Mitigation, get_session_factory
from mcp_server.auth import Caller
from mcp_server.logging_middleware import instrumented_tool

logger = logging.getLogger("aiops_copilot.mitigations")

_SessionFactory = get_session_factory()

ACTION_TEMPLATES_BY_ROOT_CAUSE = {
    "database_connection_pool_exhaustion": "scale connection pool +20% for {service}",
    "downstream_service_timeout": "increase downstream timeout and add circuit breaker for {service}",
    "memory_leak": "restart affected {service} instances on a rolling basis",
    "bad_deploy_config_change": "roll back the most recent deploy for {service}",
    "cache_stampede": "enable request coalescing on the {service} cache layer",
}
DEFAULT_ACTION_TEMPLATE = "restart affected {service} instances on a rolling basis"


async def _propose_mitigation_impl(
    ctx: Context,
    caller: Caller,
    incident_id: int,
) -> dict[str, Any]:
    session = _SessionFactory()
    try:
        incident = session.get(Incident, incident_id)
        if incident is None:
            raise MCPError(INVALID_PARAMS, f"No incident with id {incident_id}")

        template = ACTION_TEMPLATES_BY_ROOT_CAUSE.get(incident.root_cause, DEFAULT_ACTION_TEMPLATE)
        proposed_action = template.format(service=incident.service_name)

        mitigation = Mitigation(
            incident_id=incident.id,
            proposed_action=proposed_action,
            status="drafted",
        )
        session.add(mitigation)
        session.commit()
        session.refresh(mitigation)

        return {
            "draft_id": mitigation.draft_id,
            "incident_id": incident.id,
            "proposed_action": proposed_action,
            "status": mitigation.status,
        }
    finally:
        session.close()


async def _confirm_mitigation_impl(
    ctx: Context,
    caller: Caller,
    draft_id: int,
    approved: bool,
) -> dict[str, Any]:
    # Unconditional kill switch — checked before anything else, so a disabled
    # deployment refuses even a correctly-authorized approval.
    mitigations_enabled = os.environ.get("MITIGATIONS_ENABLED", "false").lower() == "true"
    if not mitigations_enabled:
        return {"draft_id": draft_id, "status": "disabled", "message": "mitigations are currently disabled"}

    if not caller.can_approve_mitigations:
        raise MCPError(
            INVALID_REQUEST,
            f"Caller '{caller.caller_id}' is not authorized to approve mitigations "
            "(the API key used for this call does not carry can_approve_mitigations).",
        )

    session = _SessionFactory()
    try:
        mitigation = session.get(Mitigation, draft_id)
        if mitigation is None:
            raise MCPError(INVALID_PARAMS, f"No mitigation draft with id {draft_id}")
        if mitigation.status != "drafted":
            raise MCPError(
                INVALID_REQUEST,
                f"Mitigation draft {draft_id} is already '{mitigation.status}'; cannot confirm again.",
            )

        if not approved:
            mitigation.status = "rejected"
            mitigation.approved_by = caller.caller_id
            mitigation.approved_at = datetime.utcnow()
            session.commit()
            return {
                "draft_id": draft_id,
                "status": "rejected",
                "message": f"Mitigation draft {draft_id} was not approved; no action taken.",
            }

        mitigation.status = "approved"
        mitigation.approved_by = caller.caller_id
        mitigation.approved_at = datetime.utcnow()
        session.commit()

        execution_log = (
            f"[SIMULATED EXECUTION] action='{mitigation.proposed_action}' "
            f"incident_id={mitigation.incident_id} approved_by={caller.caller_id} "
            f"draft_id={draft_id} — no real action was taken against any system."
        )
        logger.info(execution_log)

        mitigation.status = "executed"
        session.commit()

        return {
            "draft_id": draft_id,
            "status": "executed",
            "approved_by": caller.caller_id,
            "execution_log": execution_log,
        }
    finally:
        session.close()


propose_mitigation = instrumented_tool("propose_mitigation")(_propose_mitigation_impl)
confirm_mitigation = instrumented_tool("confirm_mitigation")(_confirm_mitigation_impl)
