# Adversarial verification report

Date: 2026-08-28; updated 2026-08-30

## Scope

This audit compared the current repository against Problem Track 1 in `stage2.pdf`,
the Stage 1 `Noir_IITKanpur.pptx.pdf` concept, and the repository's requirements,
assumptions, architecture, policies, scenarios, evaluation data, scripts, API, and
dashboard. The two research documents were treated as inspiration, not binding
acceptance criteria.

## Confirmed defects fixed

1. String and numeric substitutes for boolean trust flags could bypass authorization.
2. Destructive commands in `candidate.operation` were not inspected.
3. Engineering credentials under sensitive argument keys could bypass secret checks.
4. SQL comments and literals containing `where` could mask an unbounded `DELETE`.
5. Unknown production mutations could bypass rollback requirements.
6. Source-registry edits were not visible until process restart.
7. Missing or unavailable sources were not fully protected by exact-replay drift checks.
8. An unconfigured judge could overwrite a deterministic `NO_EVIDENCE` state.
9. Evidence-backed customer account actions did not require explicit trusted approval.
10. Nested database paths were not initialized automatically.
11. The demo dashboard could bind beyond localhost and reuse history from earlier runs.

Each item above now has a regression test or an end-to-end launcher check.

## Final verification evidence

- Ruff: all checks passed.
- Pyright: 0 errors, 0 warnings.
- Pytest: 96 passed, 3 opt-in live Groq cases skipped.
- Labelled evaluation: 17/17 expected decisions.
- Fixture false-block rate: 0.0.
- Fixture unsafe-escape rate: 0.0.
- Deterministic fixture model calls: 0.
- Average checks executed: 4.59.
- Scenario files and evaluation labels match exactly, with unique event IDs.
- Policy replay and the explicitly simulated judge scripts completed.
- FastAPI and Streamlit started together through the localhost-only fresh-database
  launcher and shut down cleanly.

These are bounded fixture-level results, not proof of general accuracy, production
security, or production performance.

## Residual risks that remain intentionally open

- The SQL/shell detector is a bounded rules engine, not a full parser or sandbox.
- Claim extraction and PII detection cover only the demonstrated patterns.
- Retrieval is governed structured fact lookup, not semantic document RAG.
- The external judge contract is implemented and evidence-bound, but no real provider
  call is part of the deterministic baseline.
- Bias, prompt injection, multi-turn causal risk, load testing, multi-tenancy,
  authentication, regulatory certification, and tamper-evident audit storage remain
  outside this student PoC.
- The 17 labelled cases are too small to support production-level statistical claims.

The repository is technically coherent with the selectively implemented Stage 2
solutioning areas, but it must continue to be presented as a proof of concept rather
than a bug-free or production-ready security product.

## Demo-readiness follow-up (updated 2026-08-30)

- The raw-JSON-first dashboard was replaced with human-readable scenario, context,
  decision, route, check, evidence, audit, policy, and metric views. Raw contracts
  remain available in collapsed technical expanders.
- The Groq endpoint and free-tier model are fixed in code. The only provider secret is
  `GROQ_API_KEY`, loaded by `python-dotenv` from each teammate's ignored local `.env`;
  `.env.example` remains the committed secret-free template.
- Two more judge-routed fixtures were added. The corpus now has 17 labelled fixtures,
  and the live Groq script/test covers three evidence-bound demonstrations while the
  normal suite remains offline.
- Python 3.11.9 and exact direct demo dependencies were recorded separately from the
  existing compatible ranges.
- Dashboard expectation metadata is cross-checked against the labelled evaluation
  corpus.
- Updated verification: Ruff passed; Pyright reported 0 errors and 0 warnings; Pytest
  reported 96 passed and 3 opt-in live Groq cases skipped; all 17 labelled
  deterministic decisions matched, with zero model calls in the deterministic run.

See `PROJECT_HANDOFF.md` for the complete history and regression-prevention procedure.
