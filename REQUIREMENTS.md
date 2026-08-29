# Requirements

## Functional

1. Accept response and proposed-action events through one contract.
   Reject unsupported schema versions, malformed source lists, non-boolean trust
   flags, and engineering use-case/environment mismatches at that boundary.
2. Route events to a versioned use-case policy.
3. Calculate stakes from impact, exposure, sensitivity, and reversibility signals.
4. Select verification checks according to risk and policy.
5. Run independent checks in parallel within a verification tier.
6. Preserve `VERIFIED`, `CONTRADICTED`, `UNCERTAIN`, and `NO_EVIDENCE` as distinct evidence states.
7. Keep authorization separate from evidence.
8. Apply critical vetoes without averaging them into an overall score.
9. Return a proportional runtime action.
10. Record stop reason, latency, check count, judge calls, and cost units.
11. Store an audit record and permit replay under another policy version.
12. Capture reviewer feedback without automatically rewriting policy.
13. Bind optional model-judge classification to the accumulated redacted retrieval
    trace rather than the model's unsupported internal knowledge.
14. Require trusted approval, identity, and eligibility before a customer account
    action can be authorized.
15. Detect source-registry changes in process and snapshot missing or unavailable
    sources so exact replay cannot silently use newly available evidence.
16. Present scenario inputs, decisions, evidence, authorization, checks, policies,
    audits, and metrics in a human-readable demo view while retaining raw JSON under
    an optional technical view.
17. Keep real-provider verification explicitly opt-in and secret-safe; ordinary tests
    and the deterministic baseline must not call an external model.

## Non-functional PoC requirements

- Deterministic rules must remain effective if the optional model judge is unavailable.
- High-impact missing evidence must result in escalation or blocking, not fabricated verification.
- Raw secrets and common PII patterns must be redacted from audit records.
- Exact replay must be reproducible with the same policy checksum, source snapshots,
  and audited historical-risk snapshot; drift must be refused rather than hidden.
- The implementation must run locally with sample data.
- The demonstration must start both local services through one command and show a
  friendly UI message when the API is unavailable.
