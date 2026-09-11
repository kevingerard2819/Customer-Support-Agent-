# Annotation guide v0.2 — SpotifyCares

Status: revised after the 12-example human pilot and user-approved review. Version 0.2 is frozen for the 200-example packet. Later changes require a new version and explicit re-review of affected labels. Pilot labels are for guideline development, not test results.

## Task definition

Evaluate a text-only draft assistant for historical Spotify support messages. It can suggest a public reply and route to a human. It cannot inspect accounts, send messages, change subscriptions, contact internal teams, inspect linked images, or establish current Spotify policy. Grounding in historical replies does not establish that a recommendation remains correct today.

Auto-handling means the next public reply can be sent without human review under this scope, not that the underlying issue is resolved. A harmless clarifying question can qualify. Report clarification-only coverage separately from substantive-answer coverage. Account-specific complaints must escalate even if a generic acknowledgement is easy to generate.

## Intent labels

| Label | Include | Boundary |
|---|---|---|
| billing_subscription | Charges, refunds, cancellation, Premium activation, student/family eligibility and invitations | A failed family invitation belongs here, even when it sounds like account linking. Payment or entitlement disputes take priority over secondary playback symptoms |
| account_access_security | Login, password recovery, account linking, suspected compromise | Paid but still Free is billing unless explicit compromise is central |
| playback_app | Crashes, stops/skips, device integration, ads malfunctioning, downloads failing | Missing catalog titles without a malfunction belong to catalog |
| library_playlists | Sorting, saving, restoring playlists, missing saved music | Sorting by Recently Added is library management, not playback. New feature suggestions belong to feedback; premium loss is billing |
| catalog_availability | Missing artists/albums, release availability, incorrect track metadata, service-country availability | Playback failures across tracks belong to playback; don't infer availability from an inaccessible image |
| feedback_feature_request | Requests for new capabilities, dissatisfaction with recommendations, product feedback | How to use an existing feature is library/playback as appropriate |
| social_acknowledgement | Thanks, praise, resolved-issue acknowledgements with no outstanding request | An unresolved complaint plus thanks is not automatically social |
| other_unclear | Missing context, image-only issue, unsupported language, press/artist business requests outside consumer scope; account-feature questions such as blocking people that do not fit the other categories | Do not force account-feature questions into playback or assume they request a new feature. Retain the example and optionally note the gap |

For multiple intents, select the explicit main request; prefer billing/account access over a downstream symptom. Use optional notes for secondary intents and optional review flags for ambiguity. Do not guess intent from a future brand response. A standalone "bump" is ambiguous without preceding context; it is not sufficient evidence of thanks or a fist bump. A request for an artist's music belongs to catalog availability, even if it also contains distress requiring escalation.

## Routing labels

Use `auto_handle` or `escalate`, independently of intent. State a reason:

- `account_action`: requires private account checks, refund, cancellation by support, entitlement repair, or account recovery.
- `security_privacy`: suspected compromise or exposed personal information; never ask for credentials publicly.
- `sensitive_safety`: distress or safety content that needs human judgement, even if the primary intent is catalog or feedback.
- `insufficient_context`: missing antecedent, inaccessible image, ambiguous follow-up.
- `unsupported_language_scope`: language outside the English evaluation scope or non-consumer business request.
- `unverified_policy`: requires current pricing, eligibility, availability, limits, or product capability not established by usable evidence.
- `repeated_failure`: already tried the proposed steps or unresolved repeated support contact.
- `safe_clarification`: only non-sensitive technical details needed; no account-specific or high-risk concern.
- `safe_acknowledgement`: no outstanding action or sensitive issue.
- `supported_general_help`: general actionable answer with adequate evidence and no policy/account dependency.

The last three can support auto_handle. Escalation takes priority when more than one applies. Profanity alone does not require escalation.

## Labelling procedure

1. Read only the customer message and supplied earlier context. Do not consult later brand replies while assigning intent and routing.
2. Select intent and route. These are the only two required fields in the batch tool. A reason dropdown, review flag, and notes are optional; do not invent completed reasons when absent.
3. Changes save automatically to the local progress file. Use Export backup for a portable JSON copy. The tool records completion times and a human-entry source marker.
4. Use optional notes for acceptable-reply requirements or forbidden claims. Reply ratings and detailed reply criteria will be collected in a separate stage; intent/routing completion does not imply that stage is complete.
5. Review development examples only while tuning the system. Keep held-out labels sealed from prompt and threshold tuning. Original pilot answers remain separate from accepted reviewed labels.

The pilot contained isolated customer messages. The 200-example packet supplies available preceding parent-chain context, and marks missing parents, cycles or timestamp conflicts. No future target reply is supplied. A future reply is evidence of historical handling, not a human gold label or proof of resolution. The old pilot PDF and workbook Guide tab describe v0.1; use this guide and the new tool for v0.2.

## Reply judge rubric (draft; not yet validated)

Score each dimension 0–2: correctness, grounding, usefulness, and appropriate routing/privacy. 0 means materially wrong/unsupported; 1 means partial or ambiguous; 2 means adequate. Judge claims against supplied evidence and the stated scope. A reply fails overall if it fabricates an account action, asks for credentials publicly, makes unsupported promises, or ignores a required escalation, regardless of its average score.

Judge quality is measured against independently entered human ratings on anonymized outputs. Report per-dimension exact agreement, weighted kappa, critical false-accept counts, and every denominator; keep calibration separate from held-out validation. The frozen v2 result is in `results/reply-review-report-v2.json`.
