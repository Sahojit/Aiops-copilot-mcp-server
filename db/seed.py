"""
Seed script — populates the database with a handful of realistic fake rows
so the dashboard (Stage 5) has something to show. Not real incident data.
"""
import random
import string
from datetime import datetime, timedelta

from db.models import Incident, Commit, ToolCall, Mitigation, get_engine, get_session_factory

SERVICES = ["checkout", "payments", "auth", "search", "notifications"]
ROOT_CAUSES = [
    "database_connection_pool_exhaustion",
    "downstream_service_timeout",
    "memory_leak",
    "bad_deploy_config_change",
    "cache_stampede",
]
AUTHORS = ["jchen", "mrivera", "asingh", "kpatel", "dwilliams"]
TOOL_NAMES = ["diagnose_incident", "score_recent_commits", "recommend_model_route", "propose_mitigation"]
CALLER_IDS = ["desktop-client-1", "desktop-client-2", "ci-bot"]


def _random_sha() -> str:
    return "".join(random.choices(string.hexdigits.lower()[:16], k=10))


def seed():
    engine = get_engine()
    Session = get_session_factory(engine)
    session = Session()

    now = datetime.utcnow()

    incidents = []
    for i in range(6):
        opened = now - timedelta(hours=random.uniform(1, 72))
        status = random.choice(["open", "resolved", "resolved", "open"])
        incident = Incident(
            service_name=random.choice(SERVICES),
            opened_at=opened,
            root_cause=random.choice(ROOT_CAUSES),
            confidence=round(random.uniform(0.6, 0.95), 3),
            cascade_risk=round(random.uniform(0.1, 0.8), 3),
            status=status,
            closed_at=opened + timedelta(hours=random.uniform(0.5, 6)) if status == "resolved" else None,
        )
        session.add(incident)
        incidents.append(incident)
    session.flush()

    for i in range(10):
        session.add(
            Commit(
                sha=_random_sha(),
                service_name=random.choice(SERVICES),
                author=random.choice(AUTHORS),
                timestamp=now - timedelta(hours=random.uniform(0, 48)),
                diff_summary=random.choice(
                    [
                        "refactor connection pool sizing logic",
                        "bump dependency versions for auth library",
                        "add retry/backoff to downstream client",
                        "hotfix null pointer in checkout flow",
                    ]
                ),
                risk_score=round(random.betavariate(2, 5), 3),
                top_factors=random.sample(
                    ["touches_hot_path", "large_diff_size", "config_change", "no_code_review_approval"],
                    k=random.randint(1, 3),
                ),
            )
        )

    for i in range(25):
        tool_name = random.choice(TOOL_NAMES)
        session.add(
            ToolCall(
                tool_name=tool_name,
                caller_id=random.choice(CALLER_IDS),
                args={"example_arg": "value"},
                result_summary=f"{tool_name} completed",
                latency_ms=round(random.uniform(50, 900), 1),
                cost_usd=round(random.uniform(0, 0.01), 6) if tool_name == "recommend_model_route" else 0.0,
                status=random.choice(["success", "success", "success", "error"]),
                created_at=now - timedelta(minutes=random.uniform(0, 1440)),
            )
        )

    for incident in incidents[:3]:
        session.add(
            Mitigation(
                incident_id=incident.id,
                proposed_action=random.choice(
                    [
                        "roll back last deploy",
                        "scale connection pool +20%",
                        "restart affected service instances",
                    ]
                ),
                status="drafted",
            )
        )

    session.commit()
    session.close()
    print("Seed complete.")


if __name__ == "__main__":
    seed()
