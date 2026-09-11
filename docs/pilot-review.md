# Pilot review

The user completed all 12 intent/routing pairs. On 2026-09-10 the assistant proposed six changes, discussed the ambiguity of “bump”, and the user accepted the proposed labels. The original answers remain unchanged in `annotations/pilot-human-labels.json`, `annotations/pilot.md`, and `annotations/pilot-batch.xlsx`. The reviewed version is `annotations/pilot-reviewed-labels.json`.

| Tweet ID | Reviewed intent | Reviewed route | Reason for change |
|---|---|---|---|
| 2313472 | billing_subscription | escalate | Family invitation and entitlement issue; human account checks |
| 2251335 | library_playlists | auto_handle | Playlist sorting; reply still needs supported instructions or safe clarification |
| 57576 | other_unclear | escalate | Taxonomy gap for account-feature questions and unverified product capability |
| 2076929 | other_unclear | escalate | “Bump” may mean a friendly gesture or an unresolved follow-up; context is missing |
| 832174 | catalog_availability | escalate | Artist availability request; retain escalation for sensitive content |
| 2121321 | other_unclear | escalate | Language outside the declared English-only scope |

The other six original pairs were retained. Neutral acknowledgements must not assert that an unresolved complaint is resolved. Auto-handle labels are conditional on a safe, supported next reply, not permission to invent an answer.

## Implications for the next annotation batch

- Explain playlist management versus playback failure with concrete examples.
- Explicitly include family invitations in subscription entitlement.
- Preserve missing-context examples and provide preceding context where available.
- Define where account-feature questions belong before freezing the full taxonomy; the pilot exposed a gap rather than proving the user wrong.
- Distinguish message-level eligibility for a safe next reply from the actual quality of a generated reply.

This is human review of AI-proposed adjudication for guideline calibration. It does not measure independent annotator agreement or human agreement with an LLM reply judge, and must not appear as headline model accuracy.
