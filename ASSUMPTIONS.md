# Assumptions

1. GitHub Copilot, Agentforce, Replit, and Air Canada provide real-world context; this PoC does not claim direct integration with those companies.
2. Platform adapters are represented by structured JSON events.
3. The caller supplies trusted context from an authoritative application boundary; the model does not create its own permissions or environment metadata.
   Boolean trust flags must arrive as JSON booleans, not truthy strings or numbers.
4. Sample customer and engineering records are fictitious.
5. One tenant, English content, and one demonstration jurisdiction are supported.
6. Tens of thousands of weekly events is a directional architecture assumption, not a tested throughput claim.
7. The optional model judge is independently configurable, receives the redacted
   retrieval trace accumulated before its tier, and is never the sole guard for
   deterministic critical violations. It must not treat its own knowledge as evidence.
8. The PoC focuses on hallucination/evidence failure, privacy, authorization, reversibility, and agent actions. Comprehensive bias detection is outside scope.
9. Labelled evaluation uses an isolated history store; the running API uses persistent
   history so adaptive routing can be demonstrated without contaminating benchmark results.
10. The `mock://local` judge is an explicitly simulated integration seam for an offline
    demonstration, not evidence of an external model call.
11. Only sources whose status and authority satisfy the active policy may establish
    verification; other configured sources remain visible in the audit as rejected attempts.
12. Policy and source checksums detect content drift for controlled replay. The PoC does
    not provide an enterprise document-versioning service or restore deleted content.
13. The five-action PoC deliberately maps low/medium `NO_EVIDENCE` responses to
    `REGENERATE`, not the original concept's illustrative `ALLOW WITH WARNING`, because
    the current API cannot guarantee warning preservation downstream.
14. A high-impact customer action is eligible for `ALLOW` only when the trusted
    adapter supplies verified identity, eligibility, explicit approval, and a
    policy-relevant structured claim. Missing approval or evidence fails closed.
