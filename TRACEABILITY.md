# Stage 2 technical traceability

| Stage 2 area | PoC implementation | Evidence |
|---|---|---|
| Multiple AI use cases | Engineering agent and support assistant | Four use-case policy profiles |
| Different risk and latency tolerance | LOW to CRITICAL routing and per-policy deadlines | `policies/`, risk profiler, evaluator |
| Overlapping risks | Combined privacy and evidence evaluation | `overlap-pii-contradiction.json` |
| Missing ground truth | `NO_EVIDENCE` distinct from `UNCERTAIN`; attempted sources retained | Retrieval detector and no-evidence scenario |
| Alert fatigue | Proportional actions, action-aware rollback, early stopping, false-positive correction | Decision engine, feedback history, production-read scenario |
| Agent actions | Strict boolean trust context, authorization, customer approval, entitlement, reversibility, and statement-bounded destructive SQL detection | Engineering, adversarial regression, and cancellation scenarios |
| API-only model boundary | Structured input/output middleware and minimized evidence-bound judge payload | FastAPI `POST /evaluate`, retrieval trace, judge adapter |
| Detection techniques | Rules, PII, retrieval, optional judge, history | Detector registry |
| Decision logic | Evidence matrix, authorization, vetoes, five actions | Decision engine |
| Architecture | Inline gate, tier parallelism, deadline | Evaluator |
| Governance | Policy source-status/authority gates, live registry refresh, missing/unavailable source snapshots, versions, checksums, redacted audit | Policies, source registry, SQLite audit, controlled replay |
| Feedback | Typed reviewer feedback with latest-label, false-positive, and adverse-outcome semantics | Feedback API and audit repository |
| Metrics | Error rates, latency, cost, checks, calls, stops, feedback | Evaluation harness and metrics service |

## Deliberately out of scope

Comprehensive bias detection, multi-turn causal risk, geography-specific legal
rules, load testing, real enterprise adapters, and production multi-tenancy are
documented roadmap items. Stage 2 permits selective solutioning and simulated data,
so these exclusions keep the prototype credible for a three-student team.
