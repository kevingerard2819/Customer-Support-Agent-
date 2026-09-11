# Decision log

Status: frozen for the reported v1 experiment.

1. Choose SpotifyCares after exploratory review: recurring software issues plus meaningful account-related escalation.
2. Use the primary Twitter source directly: retain original tweet IDs and archive checksum for traceability.
3. Keep the full archive out of the repo: it is about 177 MB compressed; discovery outputs are small.
4. Use deterministic reservoir sampling for discovery: avoids first-row sampling while keeping memory low; reply sampling bias is explicit.
5. Use eight provisional intents: broad enough for a small human-labelled dataset; preserve an unclear class.
6. Keep routing separate from intent: a catalog request can contain distress; a billing question can be general or account-specific.
7. Define auto-handling at next-reply level: clarify that it does not imply end-to-end resolution; separate clarification coverage.
8. Do not treat historical replies as gold answers: many contain private follow-up claims or stale policy.
9. Enter labels through an autosaving local tool with no model suggestions: preserve human provenance and avoid accidental AI prelabelling.
10. Use a small pilot before golden-set annotation: find expensive taxonomy ambiguities early.
11. Exclude discovery-connected threads from held-out evaluation: exploratory inspection should not contaminate the headline result.
12. Group and deduplicate before splitting: prevent later responses and paraphrased repeats leaking into retrieval.
13. Retain difficult messages in evaluation: missing context and safety/privacy are part of the task, not cleanup noise.
14. Provide a cached reproduction path separate from live inference: reproducible metrics should not depend on API drift or network latency.
15. Keep v1 and v2 results frozen after failure review, but version the v3 intent-specific fallback and deterministic sentiment postprocessing: improve the observed failures while marking replay on inspected examples as diagnostic rather than assigning the old scores to new behavior.
