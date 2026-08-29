# Architecture

ControlPlane is a modular monolith with a single evaluation API and pluggable detectors. A use-case policy maps risk tiers to verification tiers and decision vetoes.

## Processing sequence

1. Validate the shared event contract and fail closed when the schema version,
   source list, environment, or boolean proposed-action trust context is invalid.
2. Normalize supported policy statements into bounded structured claim units.
3. Load the requested or latest use-case policy.
4. Read historical adverse-outcome and reviewer signals for the event fingerprint.
5. Extract risk signals and calculate the risk tier.
6. Build a cheap-to-expensive tiered verification plan.
7. Execute independent checks concurrently inside each tier under one deadline.
8. Reject stale, missing, unavailable, or below-threshold sources as verification
   evidence while retaining every attempted source in the trace.
9. Continue past a local PII finding when claims still require evidence checks.
10. Stop on a critical veto, resolved combined evidence, deadline, or tier exhaustion.
11. Derive evidence and authorization states without averaging critical failures.
12. Apply decision precedence and the policy fail mode when the deadline expires.
13. Recursively redact the audit payload and persist source versions and checksums.

## Trust boundary

`candidate` is untrusted AI output. `trusted_context` must originate from an authenticated adapter or business system in a real deployment. The PoC represents it in JSON and labels it explicitly.
String or numeric substitutes for boolean authorization, approval, eligibility,
and rollback flags are rejected before routing. Evidence-backed support actions
also require explicit trusted approval.

## Verification hierarchy

- Tier 1: deterministic action, secret, PII, permission, reversibility, entitlement,
  and claim-structure checks
- Tier 2: retrieval against versioned enterprise policy facts
- Tier 3: optional external secondary judge over the accumulated retrieval trace,
  with an explicitly simulated offline path
- Historical signal: evaluated before routing so previous policy-significant adverse
  outcomes can raise stakes

The external judge receives a minimized, redacted projection containing the use case,
event type, candidate, policy-source IDs, and the retrieval detector's structured
evidence references. Its prompt requires classification only from that trace and
requires `NO_EVIDENCE` when usable evidence is absent. Actor, tenant, session,
customer, and other trusted-context fields do not cross that boundary.

## Runtime boundary

FastAPI is intentionally present to demonstrate a real middleware contract, replay,
audit, and policy endpoints. It is still one modular-monolith PoC, not a production
distributed architecture. `scripts/run_demo.py` starts FastAPI and Streamlit through
one student-friendly command while preserving their independently testable boundary.

## Replay semantics

A replay is an auditable comparison, not a new production sample. It reuses the
original policy version, historical sample size, and adverse-outcome rate; it does not
contribute to future history and refuses exact execution if an audited policy or
source checksum has drifted. A source that was missing during the original decision
is recorded explicitly, so its later appearance also blocks an exact replay.

## Decision precedence

Critical policy vetoes and denied authorization take priority. Contradicted,
missing, or uncertain evidence is then handled before localized redaction, so a
PII edit cannot hide an unresolved hallucination. A deadline applies the policy's
configured `BLOCK` or `ESCALATE` fail mode.

The original concept included an `ALLOW WITH WARNING` example for an unsupported
low-risk answer. This implementation deliberately does not expose that sixth action.
`NO_EVIDENCE` and `UNCERTAIN` return `REGENERATE` for LOW/MEDIUM responses and
`ESCALATE` for HIGH/CRITICAL cases. Proposed actions still escalate when uncertain,
because regeneration alone cannot safely resolve an action authorization or execution
ambiguity. The PoC cannot guarantee that a warning remains attached when downstream
applications display or act on an unsupported answer.

Historical risk uses a bounded adverse-outcome heuristic: `BLOCK`, `REGENERATE`,
`ESCALATE`, `INCORRECT`, and `UNSAFE_ESCAPE` count toward risk; a successful
`EDIT_REDACT` does not. Latest `FALSE_POSITIVE` feedback clears the adverse label.
