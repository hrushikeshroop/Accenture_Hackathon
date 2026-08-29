# Demo guide

## Start the PoC

```powershell
python scripts\run_demo.py --fresh-db
```

This starts both FastAPI and Streamlit on localhost with an isolated audit database,
so old demo history cannot change the expected walkthrough. The audit and feedback
remain available until the launcher stops. For development, the services can still
be started in separate terminals with a persistent database:

```powershell
uvicorn controlplane.main:app --reload
streamlit run dashboard\app.py
```

## Recommended walkthrough

1. Run `safe-file-edit.json` to show LOW risk, deterministic checks, early stop,
   and `ALLOW`.
2. Run `unbounded-delete-with-explanation.json` to show the regression fix: later
   explanatory prose containing `where` cannot hide an unbounded SQL `DELETE`.
3. Run `destructive-production-command.json` to show CRITICAL risk, a non-averaged
   veto, and `BLOCK`.
4. Run `overlap-pii-contradiction.json` to show that privacy detection does not
   skip retrieval; the contradicted claim produces `REGENERATE`.
5. Run `no-evidence-answer.json` to show that lack of evidence remains distinct
   from contradiction.
6. Run `unauthorized-cancellation.json` to show separate authorization and `BLOCK`.
   Explain that an otherwise eligible account action still requires explicit trusted
   approval; the regression suite also proves the approved path can `ALLOW`.
7. Open Audit trail to show policy version, rejected/selected sources, source
   checksums, stopping reason, latency, cost units, and redacted payloads.
8. Record reviewer feedback and show its aggregation on the Metrics page. Explain
   that `FALSE_POSITIVE` removes that adverse outcome from adaptive-history risk.
9. Run the replay demo to show that replay uses frozen history and does not train
   future routing.

## Additional terminal demonstrations

```powershell
python scripts\run_policy_replay_demo.py
python scripts\run_model_judge_demo.py
python scripts\run_all_scenarios.py
python evaluation\run_evaluation.py
```

The model-judge command clearly labels itself as a simulation. The normal scenario
and evaluation commands use isolated history for repeatability. Add
`--persistent-history` to the scenario sweep only when demonstrating adaptive
historical routing.

## Optional real Groq judge

Use a newly generated local key. Never record, commit, or package it. The repository
does not auto-load `.env`; export the variables in the same PowerShell session:

```powershell
$env:CONTROLPLANE_JUDGE_URL="https://api.groq.com/openai/v1/chat/completions"
$env:CONTROLPLANE_JUDGE_MODEL="qwen/qwen3.8-27b"
$env:CONTROLPLANE_JUDGE_API_KEY="paste-your-new-key-locally"
python scripts\run_live_judge_demo.py
```

The script uses the high-risk unsupported-guarantee fixture, reports whether the
provider call succeeded without printing the key, and preserves the final safe
decision. Any key previously shared outside the team's secret-management boundary
must be revoked rather than reused. See `PROJECT_HANDOFF.md` for the full procedure
and the opt-in Pytest command.

## Claims to avoid

- Do not claim production readiness or real company integration.
- Do not claim comprehensive bias, legal compliance, or PII coverage.
- Do not present the mock judge as a real external model call.
- Do not imply that the optional live-provider call is part of the deterministic
  15-case baseline.
- Describe the evaluation figures as results on 15 labelled PoC scenarios.
