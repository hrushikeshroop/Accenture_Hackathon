# ControlPlane.ai Architecture: Plain English Guide

## TL;DR: What This Actually Is

This is an **AI response gatekeeper**. When an AI (like a coding agent or customer support bot) wants to do something risky (deploy code, refund money, etc.), ControlPlane checks it before letting it through. Think of it as a security checkpoint that asks:
- "Does this response have truthful evidence?"
- "Is the person asking allowed to do this?"
- "Is this operation reversible if it goes wrong?"

---

## Architecture: The Big Picture

```
Client Request (e.g., "Edit this file" or "Cancel customer account")
         ↓
    ControlPlane API (FastAPI middleware)
         ↓
    1. PROFILE THE RISK
       └─ What's the base risk of this use case?
       └─ Does the request itself add more risk? (secrets, production, high-impact action)
         ↓
    2. PLAN VERIFICATION
       └─ Based on risk level, which checks should we run?
       └─ Can they run in parallel or must they run in sequence?
         ↓
    3. RUN CHECKS IN PARALLEL (within latency budget)
       └─ Does it have secrets? (secret detector)
       └─ Is there PII? (PII detector)
       └─ Does it match our knowledge base? (retrieval detector)
       └─ Is the user allowed? (permission/entitlement detectors)
       └─ Can we undo it? (reversibility detector)
       └─ Historical: did similar requests fail before? (historical detector)
       └─ Optional: ask an LLM for its opinion (judge detector)
         ↓
    4. DECIDE
       └─ Check veto rules (hard blocks)
       └─ Aggregate evidence
       └─ Make a decision
         ↓
    Decision: ALLOW | EDIT_REDACT | REGENERATE | BLOCK | ESCALATE
         ↓
    Log to audit trail + save feedback for future learning
```

---

## Risk Profile: The 4 Stages (They Call These "Tiers")

A **risk tier** is a severity level assigned to a request **before** checks run. It determines *which* checks to run and *how strict* to be.

| **Tier** | **Meaning** | **Example** |
|----------|-----------|-----------|
| **LOW** | Pretty safe; minimal checks needed | Reading a file, answering a FAQ |
| **MEDIUM** | Some risk; run more checks | Editing a dev-branch file, general support question |
| **HIGH** | Risky; run most checks | Production deployment, account refund |
| **CRITICAL** | Extremely risky; run everything, highest standards | Destroy production database, cancel enterprise account |

### How a Request Gets Its Risk Tier

1. **Base risk** (from policy): "In this use case (e.g., `engineering.production`), we assume HIGH risk by default."
2. **Add signals** (from the actual request):
   - "Oh, it's touching `main` branch?" → Add HIGH
   - "Oh, it contains a secret?" → Add CRITICAL
   - "Oh, it's a destructive SQL operation?" → Add CRITICAL
   - Result: Start with HIGH, plus all signals = **CRITICAL**

**Lookup table** (in policy YAML):
```yaml
signal_risks:
  destructive_operation: CRITICAL
  protected_branch: HIGH
  missing_rollback: CRITICAL
  exposed_secret: CRITICAL
```

---

## Verification: How We Check (Non-LLM Ways)

ControlPlane uses 10 **detectors** (checks). Most are deterministic rules:

### **Engineering Domain (code/deployment):**
1. **secret_detector**: Regex patterns for API keys, passwords
2. **engineering_action**: Parses SQL/shell commands; detects `DROP TABLE`, `rm -rf`, `DELETE FROM` without WHERE clause
3. **permission_detector**: Looks up who's running it; must be in trusted list
4. **reversibility_detector**: Does this operation have a rollback path? (Can't do a schema migration without `rollback_available=true`)

### **Support Domain (customer-facing):**
5. **pii_detector**: Regex patterns for SSN, email, phone, credit card numbers
6. **claim_extractor**: Parses customer text into structured claims ("refund me $50 for Order #123")
7. **retrieval_detector**: Checks claims against a YAML source registry (e.g., "Is Order #123 actually valid? Does the customer qualify for this refund?")
8. **entitlement_detector**: Does the customer have the right subscription tier to perform this action?

### **Cross-Domain:**
9. **judge_detector** (OPTIONAL LLM): Only if configured; asks an LLM "Does this response contradict the retrieval evidence?" This is NOT the primary check—it's supplementary.
10. **historical_signal**: "Did similar requests fail often in the past?" Uses audit trail history.

---

## The 4 Policy Profiles

A **policy** is a YAML file that says: "For use case X, here's what you care about."

| **Policy** | **Use Case** | **Base Risk** | **Timeout** | **Fail Mode** | **Key Veto Rules** |
|-----------|-----------|-----------|-----------|-----------|-----------|
| **engineering-development** | Code edits in dev | LOW | 1200ms | ESCALATE if unsure | Secrets = BLOCK, Unauthorized = BLOCK |
| **engineering-production** | Deployments to production | HIGH | 1800ms | BLOCK if unsure | Secrets = BLOCK, Destructive SQL = BLOCK, No rollback = BLOCK |
| **support-informational** | FAQs, policy questions | LOW | 1400ms | ESCALATE if unsure | *No vetoes* (more lenient) |
| **support-transactional** | Refunds, account changes | HIGH | 2200ms | BLOCK if unsure | Entitlement FAIL = BLOCK |

Each policy says: "For LOW risk, run [pii, retrieval]; for HIGH risk, add [judge, entitlement]; for CRITICAL, run all checks."

---

## Detector Sets = Which Checks Run (Determined by Risk Tier)

A **detector set** is just "the list of detectors we'll run for this risk tier."

```yaml
# From support-transactional.yaml
required_checks:
  LOW:      [pii_detector, claim_extractor, retrieval_detector]
  MEDIUM:   [pii_detector, claim_extractor, retrieval_detector, entitlement_detector]
  HIGH:     [pii_detector, claim_extractor, retrieval_detector, entitlement_detector, judge_detector]
  CRITICAL: [pii_detector, claim_extractor, retrieval_detector, entitlement_detector, judge_detector]
```

**In plain English:** 
- If it's LOW risk, check PII, extract claims, look them up in the knowledge base.
- If it's HIGH/CRITICAL, also ask "Is the customer eligible?" and optionally "Does an LLM agree?"

---

## Vetoes = The "Hard Blocks" in Policy

A **veto rule** is: "If detector X fails, **immediately block**, no matter what else is true."

```yaml
veto_rules:
  - detector: secret_detector
    statuses: [FAIL]
    decision: BLOCK
    reason: "A secret or credential must not be exposed."
  - detector: entitlement_detector
    statuses: [FAIL]
    decision: BLOCK
    reason: "The customer is not authorized for this action."
```

**Example:** Even if everything else is green, if we find a secret in the code, we BLOCK. No "maybe later" or warnings.

---

## What "Policy" Means Here

A **policy** is NOT a business rule like "refunds under $50 auto-approve." Instead, it's a **verification strategy**:

> "In production, assume HIGH risk. Run 4 checks concurrently. If secrets are found, block immediately. If entitlements fail, block immediately. If evidence contradicts the claim, regenerate. If we can't determine if they're eligible, escalate to a human."

It's a **config file**, not a business policy.

---

## The 5 Decision Actions (The Final Outcomes)

After running checks, ControlPlane picks one:

| **Action** | **Meaning** |
|-----------|-----------|
| **ALLOW** | All checks passed. Ship it. |
| **EDIT_REDACT** | The response is fine, but remove sensitive data. (E.g., sanitize PII, return "[REDACTED]" for the customer's SSN.) |
| **REGENERATE** | The response contradicts evidence or lacks proof. Ask the AI to try again. |
| **BLOCK** | A veto was triggered or authorization failed. Hard stop. |
| **ESCALATE** | Uncertainty or missing approval. Send to a human reviewer. |

---

## Why Governance & Feedback Loops?

Your frustration is valid: these terms ARE scattered throughout. Here's why they matter:

### **Governance**
- Policies are **versioned** (v1.0, v1.1, etc.) and stored in a **git-tracked YAML directory**.
- Before replay/audit-trail analysis, ControlPlane **verifies the policy hasn't changed** (checksum match).
- Sources (the knowledge base) are also **versioned and checksummed**.
- Why? **Reproducibility**: If we approved something under policy v1.0 and later changed the policy, we need to know whether the old decision still holds.

### **Feedback Loops**
- When a human reviews a decision (e.g., "This was actually okay, even though we blocked it"), they log **feedback with a type** ("false_positive", "adverse_outcome", etc.).
- This feedback goes into the **audit database** and updates the **historical signal detector**.
- Next time a *similar* request comes in, historical_detector says: "Hmm, last time we blocked this, but it was actually safe. Adjust the risk profile."
- Over time, the system learns which patterns are actually risky.

---

## Why Metrics Are "Vague"

They're not vague—they're **intentionally bounded for a PoC** (proof of concept):

```
Current baseline:
- 90 automated tests passed
- 15 scenarios; 15 matched expected action (100%)
- False-block rate: 0.0 on test cases
- Unsafe-escape rate: 0.0 on test cases
- Avg checks per scenario: 4.40
- Zero external model calls (all deterministic)
```

These are **NOT production claims**. The team deliberately avoided saying "99.9% accuracy in production." Instead:
- ✅ Deterministic checks (secrets, SQL parsing) are reliable.
- ❌ Bias detection, multi-turn reasoning, geographic legal rules = **out of scope** (future work).
- ❓ The system was tested on 15 labeled scenarios, not millions of real events.

---

## Quick Visual: One Complete Request

```
Customer calls support:
  "Can I cancel my account?"

Event arrives at ControlPlane:
  use_case: "support.transactional"
  operation: "account_cancellation"
  trusted_context: { customer_id: "C123", identity_verified: true, approval_present: false }

RISK PROFILING:
  → Base risk: HIGH (transactional)
  → Signals found: high_impact_action=CRITICAL, missing_approval=CRITICAL
  → Final tier: CRITICAL

PLAN:
  → For CRITICAL tier, required_checks = [pii_detector, claim_extractor, retrieval_detector, entitlement_detector, judge_detector]
  → Run pii, claim_extractor, retrieval in parallel (tier 1)
  → Wait for results

CHECKS:
  ✓ pii_detector: PASS (no SSN/email in response)
  ✓ claim_extractor: PASS (structured claim parsed)
  ✓ retrieval_detector: PASS (customer C123 exists, subscription is current)
  
  After tier 1, decision engine checks:
  → Early-stop condition? No.
  
  → Run tier 2 (entitlement_detector):
  ✗ entitlement_detector: FAIL (customer not on "premium" plan that allows self-cancellation)

DECISION:
  → VETO HIT: entitlement_detector failed → BLOCK
  → Action: BLOCK
  → Reason: "The customer is not authorized for this action."

OUTPUT:
  {
    "decision": "BLOCK",
    "risk_profile": {"tier": "CRITICAL"},
    "checks_selected": ["pii_detector", "claim_extractor", "retrieval_detector", "entitlement_detector"],
    "stop_reason": "CRITICAL_VETO",
    "latency_ms": 340
  }

AUDIT:
  → Save decision, all check results, redacted event to SQLite
  → Later, human reviews: "Actually, customer should be allowed—upgrade their plan first"
  → Feedback recorded: type="false_positive"
  → Next time a similar customer requests cancellation, historical detector factors this in
```

---

## Summary

It's not as complex as it sounds—it's just a **smart gate** that runs a sequence of checks and makes a decision. The terminology is dense because it's trying to cover real enterprise concerns (auditability, reversibility, governance, feedback), but the core is straightforward:

1. **Risk Profile** = How dangerous is this request?
2. **Detector Set** = Which checks should we run based on that risk?
3. **Vetoes** = Hard rules that immediately block, no exceptions.
4. **Policy** = The YAML config that ties it all together.
5. **Feedback Loops** = Learning from past decisions to improve future ones.
6. **Governance** = Tracking what policy version was used so decisions are reproducible.
