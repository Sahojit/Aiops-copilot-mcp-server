# AIOps Copilot

An MCP server that unifies three ML services — an incident root-cause
classifier, a git commit bug-risk scorer, and a cost-aware model routing
engine — into tools an MCP client (like Claude Desktop) can call to triage a
production incident conversationally.

**Status: Stages 1–6 built.** The three upstream services are mocked
(`mocks/`) until the real ones are wired in — see each mock's docstring.

## Running it locally

```bash
docker compose up --build
```

This starts:
- `postgres` on `5432`
- `rca_mock`, `commit_risk_mock`, `arbitration_mock` on `8001`/`8002`/`8003`
- `mcp_server` (streamable-HTTP) on `8080`

Apply migrations and seed data once Postgres is up:

```bash
docker compose exec mcp_server alembic upgrade head
docker compose exec mcp_server python -m db.seed
```

(Or run those two commands locally against `localhost:5432` if you're not
running the server itself in Docker — see `.env.example`.)

## Why streamable-HTTP, not stdio

The brief calls for an `X-API-Key` header and a per-caller rate limiter —
both are HTTP concepts. Claude Desktop normally launches MCP servers over
stdio, which has no headers, so this server instead runs the `mcp` SDK's
streamable-HTTP transport on `localhost:8080/mcp`, and Claude Desktop
connects to it as a remote server (`url` + `headers` in
`claude_desktop_config.json`) rather than spawning it as a subprocess.

## Pointing Claude Desktop at it

1. Start the server (`docker compose up`, or `python -m mcp_server.server`
   locally with the mocks and Postgres already running).
2. Copy `claude_desktop_config.json`'s `aiops-copilot` entry into your
   Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`
   on macOS), or merge it if you already have other servers configured.
3. Restart Claude Desktop. The three tools — `diagnose_incident`,
   `score_recent_commits`, `recommend_model_route` — should appear.

The bundled config uses the dev API key `dev-key-desktop-1`, which maps to
caller `desktop-client-1` (see `mcp_server/auth.py` for the fallback key
table, or set `API_KEYS_JSON` to define your own).

## Auth and rate limiting

- Every tool call must carry a valid `X-API-Key` header
  (`mcp_server/auth.py`). Missing or unrecognized keys are rejected with a
  clear error before the tool runs.
- Each caller is limited to 30 calls/minute via an in-memory token bucket
  (`mcp_server/rate_limit.py`). Exceeding it returns a clear rate-limit
  error naming the caller and the limit.
- Every call — success or failure — is logged to the `tool_calls` table
  with latency, cost, and status (`mcp_server/logging_middleware.py`).

## Verifying a full round trip

With everything running:

```bash
curl -s -X POST http://localhost:8001/rca/diagnose \
  -H 'Content-Type: application/json' \
  -d '{"service_name":"checkout","metrics":{"p99_latency_ms":900,"error_rate":0.1}}'
```

...or, to exercise the real path (MCP tool call -> mock service -> logged
`tool_calls` row), call `diagnose_incident` from Claude Desktop (or any MCP
client) and then check:

```sql
SELECT tool_name, caller_id, cost_usd, status, latency_ms
FROM tool_calls ORDER BY id DESC LIMIT 5;
```

You should see a row like:

```
    tool_name     |    caller_id     | cost_usd | status  | latency_ms
-------------------+------------------+----------+---------+------------
 diagnose_incident | desktop-client-1 |        0 | success |       21.8
```

## Gated mitigation flow

`propose_mitigation(incident_id)` drafts a plausible action (e.g. "scale
connection pool +20% for checkout") and writes it to `mitigations` with
status `drafted`. It never executes anything — it only ever adds a draft row.

`confirm_mitigation(draft_id, approved)` is the only place a mitigation can
move forward, and it does so through several independent gates, checked in
this order:

1. **Kill switch first, unconditionally.** If `MITIGATIONS_ENABLED` is not
   `true`, the tool immediately returns "mitigations are currently disabled"
   — before even looking at who's calling or what they asked for.
2. **Permission check.** The caller's own API key must carry
   `can_approve_mitigations=True` (set server-side in `mcp_server/auth.py`,
   e.g. the `dev-key-approver` key mapping to `oncall-lead`). A caller
   without that flag is rejected regardless of what `approved` value it
   passes.
3. **State check.** A draft can only be confirmed once — approving or
   rejecting a draft that isn't still `drafted` is rejected with a clear
   error, so a decision can't be silently overwritten later.
4. **Simulated execution.** Only on `approved=True` past all the above does
   status move to `executed`, with a log line recorded via Python's
   `logging` module — no real action is taken against anything.

**Why an agent can't approve its own mitigation:** `can_approve_mitigations`
is looked up from the caller's authenticated identity (their `X-API-Key`
header, verified server-side against the key table) — it is never something
the tool call's arguments can set. An automated agent driving
`propose_mitigation` typically holds a non-approving key (like
`dev-key-desktop-1`); even if that same agent is tricked or instructed to
call `confirm_mitigation` with `approved: true`, the permission check uses
*its own* key's flag, not anything it claims about itself, so it fails with
"not authorized to approve mitigations." Approval requires a *different*,
separately-issued API key — one you'd hand to a human operator's own client,
not bake into the agent's config — making the human-in-the-loop gate a
structural property of who holds which credential, not a prompt convention
the agent could talk itself out of.

## Dashboard

`docker compose up` starts a Streamlit dashboard at `http://localhost:8501`
reading directly from the `tool_calls` table — total calls, error rate,
cumulative cost, calls-per-tool over time, p50/p95 latency per tool, and
error rate per tool. It auto-refreshes every `DASHBOARD_REFRESH_SECONDS`
(default 10) using Streamlit's `st.fragment(run_every=...)`. Nothing on the
page is hardcoded: with no logged calls yet it shows an empty-state message
instead of fabricated numbers.

Run it standalone (outside Docker) with:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aiops_copilot \
  streamlit run dashboard/streamlit_app.py
```

## Eval suite

`eval/synthetic_incidents.json` holds 18 labeled scenarios (a metrics
snapshot plus the root cause a real classifier should return).
`eval/run_eval.py` calls the RCA mock directly over HTTP (bypassing MCP
transport, since this evaluates the classifier, not the plumbing) and
computes precision/recall/support per class:

```bash
RCA_SERVICE_URL=http://localhost:8001 python -m eval.run_eval
```

The current, real result — **11.1% accuracy** — is written to
`eval/eval_report.md`, unmodified. That number is expected to be close to
random-chance (12.5% across 8 classes): `rca_mock.py` picks a root cause via
`random.choice()` and never reads the metrics payload, so there's no real
signal to score yet. This eval is what actually tests `diagnose_incident`'s
accuracy once `RCA_SERVICE_URL` points at the real upstream service.

## What's mocked vs. real

Everything under `mocks/` is a stand-in for a service that doesn't exist yet
here — see the docstring at the top of each mock file. Nothing else in this
repo is mocked.

## Repo layout

See `mcp_server/`, `mocks/`, `db/`, `dashboard/`, `eval/` for the pieces
built so far; `dashboard/` (Stage 5) and `eval/` (Stage 6) content lands in
later stages.
