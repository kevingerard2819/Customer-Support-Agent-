# Offline evaluation results

These are the frozen offline baseline results against the original human labels. This stage predates the Gemini agent and reply-quality evaluations reported in the repository README.

| System | Test subset | n | Intent macro-F1 (8 classes) | Auto coverage | Escalation recall | Auto-route disagreements |
|---|---|---:|---:|---:|---:|---:|
| trivial | test_representative | 120 | 0.049 | 0.0% | 100.0% | 0/0 |
| trivial | test_challenge | 30 | 0.071 | 0.0% | 100.0% | 0/0 |
| simple | test_representative | 120 | 0.191 | 22.5% | 78.1% | 7/27 |
| simple | test_challenge | 30 | 0.254 | 23.3% | 100.0% | 0/7 |
| guarded_retrieval | test_representative | 120 | 0.191 | 2.5% | 100.0% | 0/3 |
| guarded_retrieval | test_challenge | 30 | 0.254 | 3.3% | 100.0% | 0/1 |

## What is misleading about these numbers?

- Auto-route disagreement measures disagreement with a human routing label, not whether a reply is actually safe or correct.
- Always escalating achieves perfect escalation recall with zero automation. A missing rate with no automatic replies is not zero risk.
- The guarded comparator uses templates; its auto replies are acknowledgements or clarifications, not demonstrated issue resolutions.
- Macro-F1 averages all eight predefined intents, including classes absent from development training. See the manifest for training support.
- Original labels are preserved despite development-set taxonomy/reason inconsistencies; they have not had independent second-human adjudication.
- The representative set excludes duplicate/overlapping and multi-brand conversations. The challenge set is deliberately enriched and is reported separately.
- Historical responses and UI/policy claims may be stale; public DM redirects do not expose the actual resolution.
- Test results must not drive subsequent tuning. Freeze any later version before evaluation, and disclose repeated test exposure.

## Later evidence

This file covers the frozen offline baseline stage only. Final Gemini predictions, independent human reply ratings, quota-limited judge agreement, and the five-mode failure analysis are reported in the repository README and `results/reply-review-report-v2.json`.

Runtime for this run: 1.20 seconds.
