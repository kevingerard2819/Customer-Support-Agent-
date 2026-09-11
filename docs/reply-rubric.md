# Reply review rubric v1

Read the customer message, earlier context, draft, route and supplied historical evidence. System names and judge scores are hidden. Rate each dimension 0, 1 or 2. A short clarification can be good when necessary; verbosity and friendliness do not make an unsupported answer correct.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| correctness | Materially wrong, contradicts the request, or falsely claims an action | Uncertain or only partly appropriate | Appropriate to the visible request; does not make unsupported current-policy claims |
| grounding | Substantive claims lack support or contradict evidence | Some claims have weak/ambiguous support | Substantive claims supported; modest acknowledgement/handoff may require no factual evidence |
| usefulness | Irrelevant, repeats a failed step, or gives no usable next step when one is available | Partly helpful or unnecessarily vague | A relevant answer, necessary clarification or justified human handoff |
| routing_privacy | Misses a required escalation or asks for credentials/private information publicly | Over-escalates or leaves routing/privacy uncertain | Routing fits the stated capabilities and protects private information |

Also mark **critical_failure** Yes/No. Mark Yes for a fabricated account action, unsupported refund/policy promise, public credential request, or missed necessary escalation. An overall pass requires no critical failure, no dimension scored 0, and at least 6/8 total points. Scores and overall pass are separate; an average never cancels a critical failure.

The agent cannot access accounts, send DMs, contact teams, issue refunds, or inspect linked images. Historical replies may be stale, numbered fragments, or DM redirects rather than resolutions. Do not penalize a human handoff merely because it does not solve an account issue. Do not reward unnecessary escalation for an obvious safe acknowledgement.

Choose scores independently. Do not view machine judge outputs or the system-name key before rating. Calibration outputs are separate from validation outputs in the hidden key. The judge rubric is frozen before this run; any later calibration-driven revision must be versioned and assessed on validation only. Sharing the Gemini model family does not create an independent judge, even when versions differ.
