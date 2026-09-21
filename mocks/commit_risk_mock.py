"""
MOCK SERVICE — stands in for the real Commit Risk Predictor.
Not a real ML risk scorer. Returns plausible, varied fake data
so the MCP server can be built and tested end-to-end before the real
service is wired in.
"""
import random
import string
import time
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Commit Risk Predictor Mock Service")

AUTHORS = ["jchen", "mrivera", "asingh", "kpatel", "dwilliams", "lnguyen"]

DIFF_SUMMARIES = [
    "refactor connection pool sizing logic",
    "bump dependency versions for auth library",
    "add retry/backoff to downstream client",
    "change default timeout from 30s to 5s",
    "modify feature flag rollout percentage",
    "update database migration for orders table",
    "tweak caching TTL for product catalog",
    "adjust thread pool executor config",
    "hotfix null pointer in checkout flow",
    "reformat logging statements (no logic change)",
]

FACTOR_POOL = [
    "touches_hot_path",
    "large_diff_size",
    "low_test_coverage_delta",
    "config_change",
    "recent_author_incident_history",
    "touches_critical_dependency",
    "friday_afternoon_deploy",
    "no_code_review_approval",
]


class CommitQuery(BaseModel):
    service_name: str
    window_hours: Optional[int] = 24


class CommitRisk(BaseModel):
    sha: str
    author: str
    timestamp: float
    diff_summary: str
    risk_score: float
    top_factors: List[str]


class CommitRiskResponse(BaseModel):
    service_name: str
    commits: List[CommitRisk]


def _random_sha() -> str:
    return "".join(random.choices(string.hexdigits.lower()[:16], k=10))


@app.post("/commits/score", response_model=CommitRiskResponse)
def score_commits(query: CommitQuery) -> CommitRiskResponse:
    n_commits = random.randint(3, 8)
    now = time.time()

    commits = []
    for i in range(n_commits):
        risk_score = round(random.betavariate(2, 5), 3)
        factors = random.sample(FACTOR_POOL, k=random.randint(1, 3))
        commits.append(
            CommitRisk(
                sha=_random_sha(),
                author=random.choice(AUTHORS),
                timestamp=now - random.uniform(0, query.window_hours * 3600),
                diff_summary=random.choice(DIFF_SUMMARIES),
                risk_score=risk_score,
                top_factors=factors,
            )
        )

    commits.sort(key=lambda c: c.risk_score, reverse=True)

    return CommitRiskResponse(service_name=query.service_name, commits=commits)


@app.get("/health")
def health():
    return {"status": "ok", "service": "commit_risk_mock"}
