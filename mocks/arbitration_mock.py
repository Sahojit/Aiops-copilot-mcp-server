"""
MOCK SERVICE — stands in for the real Model Arbitration Engine.
Not a real cost-aware routing engine. Returns plausible, varied fake data
so the MCP server can be built and tested end-to-end before the real
service is wired in.
"""
import random
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Model Arbitration Engine Mock Service")

MODEL_CATALOG = [
    {"name": "fast-small-model", "base_latency_ms": 180, "base_cost_usd": 0.0004},
    {"name": "balanced-mid-model", "base_latency_ms": 650, "base_cost_usd": 0.0022},
    {"name": "large-frontier-model", "base_latency_ms": 2100, "base_cost_usd": 0.014},
]

REASONING_TEMPLATES = [
    "Selected {model} because it meets the {latency_budget}ms latency budget while staying under the ${cost_budget} cost budget.",
    "Chose {model} as the best tradeoff: task complexity did not require a larger model given the budgets provided.",
    "Picked {model} — cheaper options were projected to exceed the latency budget for this task description.",
    "Routed to {model} since the cost budget ruled out larger models for this request.",
]


class RoutingRequest(BaseModel):
    task_description: str
    latency_budget_ms: int
    cost_budget_usd: float
    context_tokens: Optional[int] = None


class RoutingResponse(BaseModel):
    chosen_model: str
    expected_latency_ms: float
    expected_cost_usd: float
    reasoning: str


@app.post("/route", response_model=RoutingResponse)
def recommend_route(req: RoutingRequest) -> RoutingResponse:
    feasible = [
        m for m in MODEL_CATALOG
        if m["base_latency_ms"] * random.uniform(0.8, 1.3) <= req.latency_budget_ms
        and m["base_cost_usd"] * random.uniform(0.8, 1.3) <= req.cost_budget_usd
    ]

    if not feasible:
        feasible = [min(MODEL_CATALOG, key=lambda m: m["base_cost_usd"])]

    chosen = random.choice(feasible) if len(feasible) > 1 else feasible[0]

    expected_latency = round(chosen["base_latency_ms"] * random.uniform(0.85, 1.2), 1)
    expected_cost = round(chosen["base_cost_usd"] * random.uniform(0.85, 1.2), 6)

    reasoning = random.choice(REASONING_TEMPLATES).format(
        model=chosen["name"],
        latency_budget=req.latency_budget_ms,
        cost_budget=req.cost_budget_usd,
    )

    return RoutingResponse(
        chosen_model=chosen["name"],
        expected_latency_ms=expected_latency,
        expected_cost_usd=expected_cost,
        reasoning=reasoning,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "arbitration_mock"}
