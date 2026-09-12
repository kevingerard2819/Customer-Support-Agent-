# Failure analysis

This analysis uses frozen Gemini 3.5 Flash outputs on the representative and challenge tests plus the completed 90-output blinded human reply review. The examples were inspected after their respective runs; they were not used to tune the reported systems.

## 1. Product requests and broken behavior overlap

Tweet `2746365`, “why spotify on ios is acting weird??”, was labelled `feedback_feature_request` and predicted `playback_app`. Tweet `31593`, asking for a dislike/block feature to avoid an artist, was labelled `feedback_feature_request` and predicted `other_unclear`. Three representative errors were feature request → playback and three were feature request → unclear.

**Hypothesis:** one short message can express both dissatisfaction and desired product behavior. The eight-way single-label taxonomy forces a distinction that users often do not make. Add an explicit primary-intent tie-break rule during annotation or support multi-label error type plus requested outcome.

## 2. Library, catalogue and playback boundaries are unstable

Tweet `2216049`, “is it possible to add all of takada kenta's osts on spotify?”, was labelled `library_playlists` and predicted `catalog_availability`. Tweet `2442061` described playlist songs playing instrumental substitutes on web/desktop but correctly on mobile; it was labelled library and predicted playback. Library → catalogue was the joint-most-common confusion (3 cases), and library → playback occurred twice.

**Hypothesis:** the object mentioned (“playlist”) competes with the underlying failure (“content unavailable” or “client playback”). Annotate the operation that must resolve the issue, and add counterexamples to the prompt. A second annotator is also needed to estimate taxonomy noise.

## 3. Two automatic routes conflict with the human escalation label

Tweet `1695256` complained that a promised 30 ad-free minutes ended after one song. The agent auto-handled it with an unsupported theory that an app crash can reset the timer. Tweet `1286621` asked about a missing concert presale code; the agent auto-replied that codes go to “some of the artist's biggest fans.” Both were labelled `escalate`.

**Hypothesis:** retrieved replies make a plausible explanation sound verified. Require exact evidence support for causal explanations and entitlement decisions, and automatically escalate benefits, promotions and account-specific eligibility. These are 2 disagreements among 19 auto-handled representative examples; the Wilson 95% interval is 2.9%–31.4%, too wide for a production safety claim.

## 4. The output gate prevents unsupported replies but cuts coverage

The deterministic gate changed 74 of 200 raw model outputs to escalation. It caught 51 unsupported action/link/credential requests, 17 unsupported evidence IDs, and 8 auto replies with no cited evidence; categories can overlap. For tweet `834634`, the raw answer claimed users cannot see individual playlist followers without citing evidence. For tweet `2580777`, it invented recommendation causes and suggested nonexistent or unverified settings/cache steps.

**Hypothesis:** the base model follows familiar support patterns even when retrieval does not prove them. Structured citations plus a post-generation gate are necessary, but the current regex treats every URL or action phrase alike. Verify links against an allowlist and check claims against evidence spans to recover safe coverage.

## 5. Safe fallbacks are robotic and often give no concrete handoff

For tweet `510478`, a harmless playlist-shuffle feature request triggered the link/action gate. The v1 fallback became “This needs a human support review,” which is safe but disproportionate and unnatural. The tone-v2 rewrite improved the wording but not relevance in every case. In held-out review, tweets `2305413` (Apple Watch app), `576784` (watch volume control), and `1659439` (bring back lyrics) all received essentially the same account-style DM handoff. The human reviewer marked these replies incorrect, ungrounded and useless; all three were critical failures. Gemini had 4/20 critical failures and a 75% pass rate, while the simple system had 4/20 and an 80% pass rate.

**Hypothesis:** a generic handoff optimizes against fabricated promises at the cost of relevance and brand voice. Route product requests to an acknowledgement/feedback template and reserve private account language for cases that actually involve account data. For account-email issues, a better draft is: “Sorry you're having trouble with your account email. We'll need to handle this privately, so a member of our support team can continue with you in DMs. Please don't share your email address publicly.”

**Post-evaluation fix:** v3 implements those intent-specific fallbacks. On the 20 already-inspected Gemini validation examples, it changes seven drafts and changes all four previously critical drafts into relevant feature acknowledgements or a resolved-update acknowledgement. This is diagnostic evidence only because the failures directly informed the fix; `results/posteval-v3-diagnostic.json` explicitly leaves every new human rating null.

## Fresh v3 follow-up

Thirty newly sampled, component-disjoint candidate replies were rated after v3 was frozen. All 30 passed and none was marked critical; 27 received 8/8 and three received 7/8. The partial scores exposed narrower issues: a long wait deserved more empathy, a catalogue request was arguably over-escalated, and one fallback asked for a title already included in the message.

V4 was created only after these ratings were complete. It adds wait-aware empathy, avoids repeating a catalogue-title question when a title is already supplied, and blocks promises to monitor a case or make content available. Its replay changes 7/30 frozen drafts. `results/posteval-v4-diagnostic.json` is unscored and does not reuse the v3 ratings. The 30/30 result is limited by one reviewer, a small candidate-only sample, mixed Gemini 3.5/3.8 generation, and the absence of new intent labels or judge scores.

## Practical consequence

The system is suitable as a conservative drafting aid, with every escalated or gate-rewritten draft reviewed before sending. The current evidence does not justify unattended handling of account issues, promotions, refunds, security concerns, product requests, or ambiguous follow-ups. Automatic handling should remain limited to well-grounded acknowledgements and general answers until a larger human-rated set narrows the safety interval.
