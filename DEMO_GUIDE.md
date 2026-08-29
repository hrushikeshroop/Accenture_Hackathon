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
7. With a judge provider configured, run `judge-mixed-evidence-refund.json` to show
   one verified claim and one unsupported promise reaching the evidence-bound judge.
   Then run `judge-plan-change-promise.json` to show an authorized high-impact action
   escalating because policy evidence does not support the commercial commitment.
8. Open Audit trail to show policy version, rejected/selected sources, source
   checksums, stopping reason, latency, cost units, and redacted payloads.
9. Record reviewer feedback and show its aggregation on the Metrics page. Explain
   that `FALSE_POSITIVE` removes that adverse outcome from adaptive-history risk.
10. Run the replay demo to show that replay uses frozen history and does not train
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

Use a newly generated local key. Never record, commit, or package it. Groq's endpoint
and the demo's free-tier model are fixed in code; teammates only need to create the
ignored local `.env` file and add their own key:

```powershell
Copy-Item .env.example .env
# Edit .env and set GROQ_API_KEY to your newly generated key.
python scripts\run_live_judge_demo.py

$env:CONTROLPLANE_RUN_LIVE_JUDGE="1"
pytest tests\test_live_judge_integration.py -q
Remove-Item Env:CONTROLPLANE_RUN_LIVE_JUDGE
```

macOS or Linux:

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY to your newly generated key.
python scripts/run_live_judge_demo.py

export CONTROLPLANE_RUN_LIVE_JUDGE="1"
pytest tests/test_live_judge_integration.py -q
unset CONTROLPLANE_RUN_LIVE_JUDGE
```

The terminal script and opt-in integration test evaluate all three labelled fixtures
that naturally reach the configured Groq judge after deterministic retrieval remains
unresolved:

- `judge-unavailable-escalation.json` contains a high-risk unsupported lifetime
  guarantee.
- `judge-mixed-evidence-refund.json` includes one verified refund-window claim and
  one unsupported two-hour settlement promise.
- `judge-plan-change-promise.json` is a fully authorized plan change whose 24-month
  promotional-price promise has no supporting policy evidence.

All three expect `ESCALATE`: the judge may assess only the supplied retrieval trace,
and that trace does not establish each promise. The live script reports the HTTP
timeout, policy budget, measured judge latency, call status, and final safe decision
without printing the key. Any key previously shared outside the team's
secret-management boundary must be revoked rather than reused. See
`PROJECT_HANDOFF.md` for the full procedure and the opt-in Pytest command.

## Claims to avoid

- Do not claim production readiness or real company integration.
- Do not claim comprehensive bias, legal compliance, or PII coverage.
- Do not present the mock judge as a real external model call.
- Do not imply that optional live-provider calls are part of the deterministic
  17-case baseline.
- Describe the evaluation figures as results on 17 labelled PoC scenarios.
