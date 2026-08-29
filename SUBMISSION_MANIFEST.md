# Submission manifest

The source package contains:

- `controlplane/` - middleware contracts, routing, detectors, decisions, API, audit,
  feedback, and metrics
- `policies/` - four policy profiles and a second informational-policy version
- `knowledge/` - governed and stale illustrative policy sources
- `scenarios/` - 17 labelled engineering and support events, including three
  judge-routed Groq demonstrations
- `evaluation/` - isolated deterministic evaluation harness and committed baseline;
  machine-local latest results are regenerated and excluded
- `dashboard/` - human-readable Streamlit console with raw technical expanders
- `scripts/` - one-command demo launcher plus database, scenario, replay, simulated
  judge, three-case opt-in live judge, and clean release-builder commands
- `tests/` - 98 passing safety, contract, policy, history, replay, API, scenario,
  adversarial governance, and UI tests plus three skipped opt-in live Groq cases
- `.env.example` - secret-free teammate template; `python-dotenv` auto-loads each
  ignored local `.env`, where `GROQ_API_KEY` is the only provider secret
- requirements, assumptions, architecture, limitations, traceability, and demo guide
- adversarial audit report with verified fixes, executed gates, and residual risks
- comprehensive project handoff with the behavioral history, compatibility invariants,
  resolved-defect register, provider procedure, and release checklist

Generated databases, virtual environments, caches, `.env`, secrets, and proprietary
data are excluded from the submission archive. The fixed Groq endpoint and free-tier
model remain in source code so teammates configure only their own key.

Build the archive from the repository root with
`python scripts\build_release_zip.py`. The builder uses a source allowlist, blocks a
Groq-key pattern, verifies ZIP integrity, and replaces the prior transfer archive only
after the new archive is complete.
