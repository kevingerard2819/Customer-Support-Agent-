# Spotify support agent — Hiver SDE intern assignment

This repository turns SpotifyCares conversations from the Kaggle *Customer Support on Twitter* dataset into a conservative support agent. For each incoming message it predicts one of eight data-derived intents, retrieves historical Spotify replies, drafts a cited response, and chooses `auto_handle` or `escalate` with a reason. A deterministic output gate blocks unsupported actions, links, evidence IDs, account handling and risky follow-ups.

The proof is built around 200 manually labelled messages, component-disjoint retrieval data, two baselines, cached model outputs, a blinded reply review, and separate representative/challenge results.

## Reproduce the headline result in under 15 minutes

Python 3.11+ is required. From this repository directory:

```sh
python -m pip install -r requirements.txt
python scripts/reproduce_cached.py
python -m unittest discover -s tests -v
node scripts/report_reply_review.mjs
```

The reproduction command makes no network or LLM calls. It recalculates every classification/routing metric from committed predictions and human labels and writes `results/reproduced-metrics.json`. It normally runs in seconds after dependency installation.

## Headline results

The primary result is the 120-message representative test subset. All intent macro-F1 values average the same eight predefined classes, including zero-support classes. “Route disagreement” means an auto-handled example that a human labelled for escalation.

| System | Intent macro-F1 | Auto coverage | Escalation recall | Auto-route disagreements |
|---|---:|---:|---:|---:|
| Always escalate + majority intent | 0.049 | 0/120 (0.0%) | 100.0% | 0/0 |
| TF-IDF + logistic regression | 0.191 | 27/120 (22.5%) | 78.1% | 7/27 |
| Guarded retrieval templates | 0.191 | 3/120 (2.5%) | 100.0% | 0/3 |
| Retrieval + Gemini 3.5 Flash + output gate | **0.611** | 19/120 (15.8%) | 93.8% | 2/19 |

On the 30-message challenge subset, Gemini scored 0.499 macro-F1, auto-handled 1/30, and caught all 6 human-labelled escalations. The 0/1 disagreement result has almost no statistical force: its Wilson 95% upper bound is 79.3%. Full class-level metrics and immutable run metadata are in `results/offline-v1` and `results/gemini-3.5-final-v1`.

Reply quality was independently human-rated on 90 blinded outputs: the same 10 development and 20 representative inputs crossed with the trivial, simple and Gemini systems. Thirty outputs were used for rubric calibration and sixty for held-out validation. A reply passes only if it has no critical failure, no dimension scored zero, and scores at least 6/8 across correctness, grounding, usefulness, and routing/privacy.

| System (held-out human review) | Pass rate | Critical failures | Mean correctness | Mean grounding | Mean usefulness | Mean routing/privacy |
|---|---:|---:|---:|---:|---:|---:|
| Trivial handoff | 12/20 (60%) | 5/20 (25%) | 1.40 | 1.40 | 1.50 | 1.55 |
| Simple guarded templates | **16/20 (80%)** | 4/20 (20%) | **1.55** | **1.55** | 1.50 | **1.80** |
| Gemini + output gate (`human-tone-v2`) | 15/20 (75%) | 4/20 (20%) | 1.50 | 1.50 | **1.55** | 1.70 |

The simple system narrowly beat Gemini on this small reply sample. This does not establish a stable ordering, but it blocks the claim that the LLM produced the best replies. The full ratings and generated report are in `annotations/reply-ratings-human-v2.json` and `results/reply-review-report-v2.json`.

The Gemini judge completed 60/90 calls before provider quota/capacity failures, leaving 42 held-out validation pairs. Exact agreement on validation was 54.8% for correctness, 64.3% for grounding, 61.9% for usefulness, and 69.0% for routing/privacy; linear-weighted kappa was only 0.142–0.222. More seriously, it caught 0/9 human critical failures in the paired validation subset. The judge is therefore useful only as a diagnostic here and cannot replace human review. Run `node scripts/report_reply_review.mjs` to reproduce these calculations.

A separate post-fix review then sampled 30 new conversation components excluded from discovery, the full 200-example golden packet, and retrieval. V3 passed 30/30 replies under the same human rubric with zero critical failures. Twenty-seven replies received 8/8 and three received 7/8; mean correctness, grounding, usefulness, and routing/privacy were 1.93, 2.00, 1.97, and 2.00. This is encouraging evidence that the known generic-handoff failures did not recur, but it is a small, single-reviewer sample containing only the candidate system. Gemini 3.5 generated 19 items and Gemini 3.8 generated 11 after quota was reached, and this packet has no independent intent labels or new judge scores.

## What “good” means

For this brand, a useful agent must classify recurring issues well enough to retrieve relevant precedent, never imply it accessed an account or completed a refund, protect private information, and escalate security, payment, account-specific, distress and unresolved cases. Auto-handling means the next public reply is safe; it does not mean the underlying case is resolved.

The v1 target is intentionally conservative: improve intent macro-F1 over a simple supervised baseline while auto-handling a measurable subset and retaining high recall for human-required cases. Reply quality must pass independent human review; classification accuracy alone cannot establish trust.

This project does not build account integrations, execute refunds, claim end-to-end resolution, infer facts from unavailable images/links, or establish current Spotify policy. Public Twitter replies often redirect to DMs, so the dataset does not reveal the private resolution.

## Data and labels

The pipeline scanned all 2,811,774 source rows. It reconstructs undirected conversation components from parent/response links, removes components seen during exploration, excludes multi-brand threads, normalizes near-duplicates, and selects at most one target per component. The 200 labelled messages are split into 50 development, 120 representative test and 30 challenge examples. Thirty-six contain available earlier context. Retrieval uses 4,440 historical customer/support pairs from components disjoint from all labelled and discovery examples; each record explicitly says `resolution_verified=false`.

The candidate labelled all 200 examples using the autosaving local tool and guide v0.2. No model suggestions were shown. Labels include eight intents (`billing_subscription`, `account_access_security`, `playback_app`, `library_playlists`, `catalog_availability`, `feedback_feature_request`, `social_acknowledgement`, `other_unclear`) and a separate route. Sampling, deduplication limits and provenance are documented in `docs/batch-sampling.md`; the machine-readable split is `data/split-manifest.json`.

## System design

1. TF-IDF similarity retrieves old Spotify customer/reply pairs without using evaluation components.
2. Gemini receives the message, available earlier context, intent guide and retrieved evidence. It returns structured intent, route, reason, draft, reply type and evidence IDs.
3. A deterministic sentiment signal (`positive`, `neutral`, `negative`, `mixed`, or `distressed`) adjusts tone without deciding escalation from negativity alone. Explicit distress continues into the safety route.
4. Exact-ID validation rejects malformed batches. A local gate escalates unsupported citations, action/refund claims, unsafe links, uncited automatic replies and predefined account/follow-up risks.
5. Cached accepted outputs make evaluation reproducible despite provider drift and rate limits.

Gemini 3.8 and 3.7 were attempted first for the agent but repeatedly returned provider capacity/quota failures; Gemini 3.5 Flash completed the frozen agent run. The reply judge used 45 cached Gemini 3.5 ratings and 15 Gemini 3.8 ratings before 3.8 hit quota; attempts to continue with 3.7 and 3.6 ended in capacity errors. All judge versions are from the same model family as the agent, creating correlated-error risk, so human validation is primary.

## Failure analysis

The five inspected modes are documented with tweet IDs, messages and hypotheses in `docs/failure-analysis.md`:

1. feature requests overlap broken behavior;
2. library, catalogue and playback boundaries are unstable;
3. plausible retrieved explanations caused two unsafe route disagreements;
4. the gate prevented 74 questionable raw outputs but reduced coverage;
5. generic gated handoffs are safe in form but can be irrelevant enough to fail human review.

The last mode remained visible after the tone rewrite. Four of 20 Gemini validation replies were marked critical failures by the human reviewer. Requests for an Apple Watch app, watch volume controls and lyrics were all replaced with account-style DM handoffs, discarding the user’s actual request.

The blinded comparative review tested `human-tone-v2`. Its generic gate fallback caused four Gemini critical failures. V3 added intent-specific fallbacks: account and billing cases retained a private DM handoff, while feature, catalogue, playback, library, acknowledgement, and unclear cases received separate safe replies. Reapplying v3 to frozen raw outputs changed 7/20 Gemini validation drafts, including all four previously critical examples. V3 was then assessed in the separate 30-item review above.

Three v3 replies lost one point: a five-year feature wait needed more empathy, a catalogue request was arguably over-escalated, and a catalogue clarification asked for a title already present in the message. After ratings were frozen, v4 improved wait-aware empathy, stopped repeating the title question, and blocked promises to monitor or make content available. Replaying v4 changed 7/30 drafts. `results/posteval-v4-diagnostic.json` is explicitly unscored; the v3 ratings are not transferred to it.

The deterministic sentiment signal was also added after the v2 review packet was frozen. Its dataset profile is reproducible with `python scripts/summarize_sentiment.py`. It is not presented as validated sentiment accuracy and does not change routing merely because a user sounds negative.

V3 also passes 20/20 fresh, hand-authored adversarial response scenarios in `tests/external_response_cases.json`. They cover refund promises, duplicate charges, password exposure, hacked accounts, prompt injection, fake citations, invented DMs/forwarding, unsafe links, feature requests, playback, library/catalogue clarification, positive updates, distress, and unresolved follow-ups. The full suite contains 22 tests. This outside suite exercises the deterministic response gate with supplied intents and hostile raw drafts; it does not measure live Gemini intent classification or human preference.

## What is misleading about my headline number?

- **0.611 macro-F1 is not reply quality.** A correctly named intent can still produce an unsafe or useless response.
- **2/19 is not a stable safety rate.** Its Wilson 95% interval is 2.9%–31.4%; 120 representative messages are too few for a production claim.
- **Always-escalate looks perfectly safe on escalation recall.** It delivers zero automation, and 0/0 route disagreements is undefined rather than zero risk.
- **The representative population is filtered.** It covers replied-to, single-brand, nonduplicate Spotify tweets with usable text, not all incoming support traffic or present-day users.
- **The challenge set changes prevalence.** It is intentionally enriched for short, repeated and sensitive cases and is never pooled into the headline.
- **Labels have one annotator.** Taxonomy boundary noise is visible in library/catalogue/playback errors; no second-human kappa is claimed.
- **Historical replies are not verified resolutions.** They may be stale fragments or public DM redirects.
- **The test was inspected after freezing v1.** Failure analysis uses test errors, so any fixes require a new untouched test set.
- **The gate trades usefulness for safety.** It rewrote 74/200 raw responses; final coverage partly reflects conservative regex rules rather than model judgment.
- **The LLM did not win reply quality.** On only 20 held-out replies per system, Gemini passed 75% versus 80% for the simple templates. The sample is too small for a stable ranking, while the four Gemini critical failures rule out unattended use.
- **The automated judge is not a substitute for a human.** Only 42/60 validation outputs were paired because of provider limits, its weighted kappas were 0.142–0.222, and it missed all nine human critical failures in that subset.
- **30/30 post-fix reply passes is not a production guarantee.** It is one reviewer rating 30 candidate-only outputs, with no contemporaneous baselines, independent intent labels, or automated-judge comparison. The run also mixes 19 Gemini 3.5 and 11 Gemini 3.8 outputs after quota exhaustion.

## With one more week

First, add a second annotator for a stratified 60-example subset and adjudicate taxonomy/routing disagreements. Next, replace regex-only grounding with evidence-span entailment and an allowlist of current official Spotify links. Create reason-specific, approved handoff templates so gated replies remain natural and actionable. Collect at least several hundred new representative messages, including temporal and non-English slices, then set automation thresholds against a predeclared critical-failure ceiling with confidence bounds. Finally, use a judge from a different model family and validate any rubric changes on a fresh held-out reply set.

## Optional workflows

Run the live agent only when a Gemini key is available locally; never commit it:

```sh
python scripts/run_gemini.py --model gemini-3.5-flash --key-file path/to/key.txt --output results/new-run
python scripts/build_posteval_v3.py
```

For manual end-to-end testing, run `python scripts/try_live_agent.py --model gemini-3.5-flash` and open `http://127.0.0.1:8766`. Enter a Gemini key once in the local page; it stays only in server memory. Alternatively pass `--key-file path/to/key.txt`. The page runs actual retrieval, Gemini classification/drafting, and the deterministic output gate. Test messages and retrieved historical snippets are sent to Gemini; the key is never displayed or committed.

The post-fix v3 reply review uses 30 newly sampled conversation components excluded from discovery, the 200-example golden packet, and retrieval. Its source packet and model outputs are frozen in `annotations/fresh-reply-eval-v3-source.json` and `results/gemini-v3-fresh`. Gemini 3.5 produced the first 19 replies; after its quota was reached, Gemini 3.8 produced the remaining 11, as recorded in the run manifest. Reproduce its completed human report with `python scripts/report_fresh_reply_review.py`. The current live runner contains the later, unscored v4 wording guardrails.

Open the autosaving label and reply-review tools on Windows with `open-labels.ps1` and `open-reply-review.ps1`. Dataset preparation commands and archive checksum are documented in `docs/batch-sampling.md` and `docs/discovery.md`.

## Attribution

Dataset: [Thought Vector, Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter), listed as CC BY-NC-SA 4.0. Included excerpts remain under the dataset licence. Code and documentation were produced with AI coding assistance and reviewed through the candidate’s labelling and reply-rating workflows; the candidate should be prepared to explain and modify them live.
