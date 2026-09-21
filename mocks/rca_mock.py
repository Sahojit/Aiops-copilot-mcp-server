"""
MOCK SERVICE — stands in for the real AIOps RCA service.
Not a real root-cause classifier. Returns plausible, varied fake data
so the MCP server can be built and tested end-to-end before the real
service is wired in.
"""
import random
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="AIOps RCA Mock Service")

ROOT_CAUSES = [
    "database_connection_pool_exhaustion",
    "downstream_service_timeout",
    "memory_leak",
    "bad_deploy_config_change",
    "cpu_throttling",
    "cache_stampede",
    "dns_resolution_failure",
    "disk_io_saturation",
]

FACTOR_POOL = [
    "p99_latency_spike",
    "error_rate_increase",
    "connection_pool_utilization",
    "gc_pause_time",
    "queue_depth",
    "upstream_5xx_rate",
    "cpu_throttle_events",
    "disk_iops",
    "cache_hit_ratio_drop",
    "recent_deploy_correlation",
]


class MetricsSnapshot(BaseModel):
    service_name: str
    metrics: dict
    window_minutes: Optional[int] = 15


class ShapFactor(BaseModel):
    name: str
    contribution: float


class RCAResponse(BaseModel):
    root_cause: str
    confidence: float
    shap_top_factors: List[ShapFactor]
    cascade_risk: float


@app.post("/rca/diagnose", response_model=RCAResponse)
def diagnose(snapshot: MetricsSnapshot) -> RCAResponse:
    root_cause = random.choice(ROOT_CAUSES)
    confidence = round(random.uniform(0.55, 0.97), 3)
    cascade_risk = round(random.uniform(0.05, 0.9), 3)

    chosen_factors = random.sample(FACTOR_POOL, k=random.randint(2, 4))
    weights = sorted((round(random.uniform(0.05, 0.45), 3) for _ in chosen_factors), reverse=True)
    top_factors = [
        ShapFactor(name=name, contribution=weight)
        for name, weight in zip(chosen_factors, weights)
    ]

    return RCAResponse(
        root_cause=root_cause,
        confidence=confidence,
        shap_top_factors=top_factors,
        cascade_risk=cascade_risk,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "rca_mock"}
