# ControlPlane.ai

ControlPlane.ai is an adaptive verification middleware for enterprise AI responses and proposed agent actions. It sits between an existing AI workflow and its downstream user or tool, selects checks according to risk and reversibility, applies a versioned policy, and returns a proportional runtime decision.

This repository is a bounded proof of concept for Accenture Innovation Challenge 2026, Problem Track 1. It is not a production security product and does not claim integration with any named company.

## Problem

Enterprise AI controls usually fail in one of two ways:

- every interaction receives the same expensive verification, increasing latency, model cost, and manual-review load; or
- high-consequence responses and agent actions pass through insufficient evidence, privacy, authorization, or reversibility checks.

The required control depth depends on the use case, proposed consequence, trusted application context, available evidence, and the cost of being wrong. ControlPlane.ai demonstrates how one middleware instance can enforce different policies for multiple AI workflows without building a large surrounding SaaS application.

## Demonstration scope

The PoC models one fictitious B2B SaaS company with two AI touchpoints:

1. An internal coding and deployment agent that proposes file edits, commands, migrations, and deployment actions.
2. A customer-support assistant that produces policy answers and proposes account actions.

Four policy profiles give these workflows different base risks, latency budgets, detector sets, vetoes, fail modes, and reversibility requirements.
Proposed customer actions additionally require strictly typed trusted identity,
eligibility, and approval signals; missing approval is escalated rather than inferred.

## Core mechanism

```text
AI response or proposed action
            |
            v
structured ControlEvent contract
            |
            v
risk profile -> verification plan -> tier-local parallel checks
            |
            v
evidence + authorization + policy + reversibility
            |
            v
ALLOW | EDIT_REDACT | REGENERATE | BLOCK | ESCALATE
            |
            v
redacted audit | replay | feedback | metrics
```

The five outcomes are intentionally different:

- `ALLOW`: mandatory checks resolve without a policy violation.
- `EDIT_REDACT`: localized sensitive content can be removed safely.
- `REGENERATE`: a response conflicts with evidence or remains unsupported/uncertain at LOW or MEDIUM risk.
- `BLOCK`: a critical policy, authorization, secret, or reversibility rule fails.
- `ESCALATE`: HIGH/CRITICAL uncertainty, missing approval, or an unresolved high-risk check requires a human.

The original concept considered allowing some unsupported low-risk answers with a
warning. This PoC deliberately tightens that behavior: `NO_EVIDENCE` or `UNCERTAIN`
produces `REGENERATE` for LOW/MEDIUM responses and `ESCALATE` for HIGH/CRITICAL cases. The
five-action API has no warning-bearing allow state, and the demo does not release an
unsupported customer-facing claim merely because its immediate impact appears low.

## Stage 2 solutioning coverage

| Stage 2 area | PoC mechanism |
|---|---|
| Detection | Deterministic rules including statement-bounded destructive SQL checks, PII and secret checks, governed retrieval, historical signal, and an optional evidence-bound secondary model judge |
| Decision logic | Risk tiers, separate evidence and authorization states, critical vetoes, and five graded actions |
| Architecture | Inline FastAPI middleware, tier-local concurrency, early stopping, and one policy deadline |
| Governance | Versioned YAML policies, live source-registry refresh, source authority and availability, checksums, redacted audit, and drift-refusing replay |
| Feedback loops | Typed reviewer outcomes with latest-label and false-positive semantics |
| Metrics | Decisions, stops, latency, check count, cost units, model calls, and reviewer feedback |

See `TRACEABILITY.md` for the full mapping to Track 1 complexities.

## Technology stack

- Python 3.11 or newer; Python 3.11.9 is the verified demo runtime
- FastAPI and Uvicorn for the middleware API
- Pydantic for typed event and decision contracts
- YAML for policy and governed-source configuration
- SQLite for local redacted audit and feedback records
- Streamlit for the lightweight demonstration console
- Pytest for automated verification

The default deterministic path requires no external LLM API key.

## Repository structure

```text
controlplane/       Core contracts, routing, detectors, decisions, audit, API, and metrics
policies/           Four use-case policy profiles plus one historical policy version
knowledge/          Approved, stale, and current illustrative source documents
scenarios/          Seventeen labelled events, including three judge-routed demos
evaluation/         Deterministic evaluation harness and committed baseline summary
dashboard/          Lightweight Streamlit console
scripts/            Scenario, replay, initialization, simulated-judge, and live-judge demos
tests/              Scenario, policy, API, replay, security, UI, and opt-in live tests
```

Start future maintenance by reading `PROJECT_HANDOFF.md`. It records the behavioral
history, fixed-defect register, compatibility invariants, provider safety procedure,
and release checklist.

## Local setup

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-demo.txt
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-demo.txt
```

Initialize the local database, then start the API and dashboard together:

```powershell
python scripts\initialize_database.py
python scripts\run_demo.py --fresh-db
```

For development, the two services can still be started separately:

```powershell
uvicorn controlplane.main:app --reload
streamlit run dashboard\app.py
```

Open:

- API documentation: `http://localhost:8000/docs`
- Streamlit dashboard: the local URL printed by Streamlit

`--fresh-db` keeps the live demo reproducible by using an isolated audit database
for that run. Omit it only when you intentionally want history to persist across
separate launcher sessions.

## Configuration

Create a machine-local `.env` from the teammate-safe template:

```powershell
Copy-Item .env.example .env
```

Set only your own `GROQ_API_KEY` in `.env` to enable live judging. The application
auto-loads this ignored file through `python-dotenv`; existing shell or CI variables
still take precedence. Share `.env.example`, never `.env` or a real key.

The Groq chat endpoint (`https://api.groq.com/openai/v1/chat/completions`) and free-tier
model (`qwen/qwen3.8-27b`) are fixed in code for this demo. Teammates do not need to
export or configure either value.

The optional external judge expects an OpenAI-compatible chat-completions response
shape. It receives a minimized, redacted candidate plus the retrieval detector's
structured evidence trace and is instructed not to use model knowledge as evidence.
It is never the sole guard for deterministic critical violations. The included
`mock://local` path is explicitly simulated and must not be presented as a real model
call.

To run all three real evidence-bound judge demonstrations after adding the key:

```powershell
python scripts\run_live_judge_demo.py

$env:CONTROLPLANE_RUN_LIVE_JUDGE="1"
pytest -m live -q
```

The three calls deliberately show different proportional outcomes: the MEDIUM-risk
informational case regenerates automatically, while HIGH/CRITICAL unsupported
commitments escalate. The normal test suite skips these network cases. See
`PROJECT_HANDOFF.md` for the key revocation warning, cleanup commands, and failure
semantics.

## Example API request

The easiest reproducible request is to load one of the JSON files under `scenarios/` and send it to `POST /evaluate`.

```powershell
$event = Get-Content -Raw scenarios\engineering\safe-file-edit.json
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/evaluate `
  -ContentType application/json `
  -Body $event
```

Important response fields include:

```json
{
  "risk_profile": {"tier": "LOW"},
  "decision": "ALLOW",
  "stop_reason": "RESOLVED",
  "policy_version": "1.0",
  "checks_selected": [],
  "check_results": [],
  "latency_ms": 0,
  "estimated_cost_units": 0,
  "model_calls": 0
}
```

The values above illustrate the response contract. Run the scenario to obtain actual check lists, timing, and cost-unit values for the local environment.

## API endpoints

- `GET /health` - health check
- `POST /evaluate` - evaluate one candidate response or proposed action
- `GET /evaluations` - inspect the redacted audit trail
- `GET /evaluations/{id}` - inspect one evaluation
- `POST /evaluations/{id}/replay` - controlled replay under an original or selected policy version
- `POST /feedback` - record a typed reviewer outcome
- `GET /policies` - inspect active and historical policies
- `GET /metrics` - inspect runtime and reviewer-feedback metrics

## Verification commands

```powershell
pytest
python scripts\run_all_scenarios.py
python evaluation\run_evaluation.py
python scripts\run_policy_replay_demo.py
python scripts\run_model_judge_demo.py
```

Current repository verification:

- 98 automated tests passed; 3 opt-in live Groq cases skipped by default.
- 17 of 17 labelled deterministic fixtures matched their expected actions.
- False-block rate was 0.0 on the included labelled fixtures.
- Unsafe-escape rate was 0.0 on the included labelled fixtures.
- Average checks executed were 4.53 per scenario.
- The deterministic baseline made zero external model calls.

These figures are fixture-level PoC results, not claims of general accuracy, production latency, or production safety. See `evaluation/results/baseline.json` for the committed summary and rerun the harness for local timing.

## Recommended demonstration

1. `safe-file-edit.json` - low risk, early stop, `ALLOW`.
2. `unbounded-delete-with-explanation.json` - an unsafe SQL command remains detectable even when later prose contains the word `where`; critical veto, `BLOCK`.
3. `destructive-production-command.json` - another critical veto, `BLOCK`.
4. `overlap-pii-contradiction.json` - overlapping privacy and evidence risk, `REGENERATE`.
5. `no-evidence-answer.json` - no evidence remains distinct from contradiction.
6. `unauthorized-cancellation.json` - authorization failure, `BLOCK`.
7. Audit trail - policy version, source decisions, checksums, stopping reason, redaction, latency, and cost units.
8. Reviewer feedback and metrics - show how typed feedback changes adverse-outcome history semantics.
9. Replay demonstration - use frozen history without training future routing.
10. Groq judge demo - run the three judge-routed support cases with one local
    `GROQ_API_KEY` and show their evidence-bound, fail-closed decisions.

See `DEMO_GUIDE.md` for the full walkthrough.

## Assumptions and limitations

- Platform integrations are simulated with structured JSON events.
- The caller supplies trusted application context; the candidate model cannot create its own permissions.
- Trust flags use exact JSON booleans; strings such as `"false"` are rejected.
- Sample customer, policy, and engineering records are fictitious.
- One tenant, English content, and local execution are supported.
- The API has no production authentication, tenant boundary, or hosted security perimeter.
- Claim extraction, command parsing, PII detection, and retrieval are intentionally bounded for the demonstration.
- Retrieval is structured key-value fact lookup against the YAML source registry, not semantic search over the Markdown documents.
- Comprehensive bias detection, prompt-injection coverage, geography-specific legal rules, multi-turn causal risk, load testing, and production monitoring remain future work.
- SQLite and Streamlit are PoC components, not the proposed production architecture.
- No real external LLM call is required by the deterministic baseline. A separate
  environment-gated Groq integration test and demo are available.

See `ASSUMPTIONS.md` and `KNOWN_LIMITATIONS.md` for the complete lists.

## Team

Team Noir, IIT Kanpur

- M. Enoch Emmanuel
- Jayanth Matam
- Hrushikesh Roop Avvari

## Submission note

The public GitHub repository is the source-of-truth code submission. Generated databases, caches, local secrets, and virtual environments must not be committed. The prototype video and detailed business proposal are submitted separately through the challenge portal.
