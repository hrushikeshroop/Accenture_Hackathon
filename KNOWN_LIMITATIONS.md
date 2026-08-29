# Known limitations

- JSON fixtures simulate platform adapters.
- The command detector is a bounded rules engine, not a complete shell or SQL parser.
  Its unbounded-`DELETE` check recognizes statement and prose boundaries but does not
  attempt full dialect-aware SQL parsing.
- Claim extraction is a bounded deterministic parser for a few demo policy claims;
  a general claim-extraction model or platform adapter is future work.
- The model judge is optional and provider-configurable. The offline judge
  demonstration is explicitly simulated. A separate opt-in Groq integration path is
  available, but it is not executed by the deterministic baseline and remains subject
  to provider availability, rate limits, preview-model changes, and network latency.
- Historical routing uses small PoC samples and is illustrative, not statistically calibrated.
- Historical risk is an adverse-outcome heuristic. Successful `EDIT_REDACT` events do
  not raise it unless reviewer feedback later labels the result incorrect or unsafe.
- SQLite and the local dashboard are not production architecture.
- The local API has no production authentication, tenant boundary, rate limiting,
  or hosted security perimeter. The bundled launcher therefore binds both services
  to localhost only.
- Policies demonstrate configuration and versioning but do not claim legal compliance.
- Regex PII detection covers common emails, cards, credentials, and phone formats;
  comprehensive entity recognition is outside the PoC.
- Structured retrieval compares bounded claims with facts in the YAML source registry;
  it is not embedding-based semantic RAG over arbitrary documents.
- Policies are cached in process and refreshed when policy file metadata changes. The
  PoC does not implement distributed cache invalidation across multiple API instances.
- Source checksums detect replay drift but do not archive or restore old source content.
- A support action without a policy-relevant structured claim fails closed with
  `NO_EVIDENCE`; general action-precondition extraction is outside this PoC.
- Timing out the optional external judge fails the decision safely, but the underlying
  blocking HTTP worker may finish after the evaluator deadline.
- Session IDs are audited, but multi-turn causal/compounding-risk analysis is not implemented.
- Bias evaluation, adversarial prompt-injection coverage, load testing, and
  multi-tenant isolation remain roadmap work.
