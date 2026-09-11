# 200-example batch: sampling and labelling

Guide version: 0.2. Seed: 20260910. The machine-readable packet fingerprint, split IDs and counts are in `data/split-manifest.json`.

## Sampling population

The pipeline scanned all 2,811,774 rows in the original Kaggle archive. Both parent IDs and response IDs create undirected conversation edges, including absent linked tweets. Spotify-connected components are retained in a second pass. Components containing another brand and components touched by exploratory discovery are excluded. One directly answered customer message is selected randomly per eligible component, and the component order is shuffled deterministically. Pure mention-only/URL-only inputs with no normalized word content are excluded.

The initial sample has 50 development examples and 120 representative test examples. A separate 30-example challenge subset is selected from remaining components using predefined security/privacy/sensitive terms, short follow-ups, or repeated-issue terms. These heuristics select challenges; they do not assign labels. Challenge examples comprise 5 sensitive/security/privacy matches, 3 short follow-ups, and 22 repeated-issue matches.

The resulting 200 messages belong to 200 distinct conversation components. Thirty-six have earlier context. None of the selected parent chains has a detected missing parent, cycle or timestamp conflict. This does not prove full conversations or linked media are present. The actual response to the target message is never included in the packet. Split and challenge metadata are not displayed in the labelling window to avoid priming labels.

## Leakage and duplicate controls

Known discovery components are excluded before selection. Customer text is normalized by removing mentions/URLs, case-folding and keeping Unicode word tokens. Short messages use exact normalized matches; longer messages use word-trigram Jaccard similarity of at least 0.8. Similarity exclusions apply against discovery messages and previously selected targets. One target per component prevents conversation overlap between development and test.

For retrieval, exclude all sampled and discovery components, then remove any remaining component whose customer messages match the same text-overlap rule. This removed 998 additional candidate retrieval components. Select 3,000 remaining components deterministically, yielding 4,440 linked customer/support pairs. A pair is historical handling evidence, not a verified resolution; every pair explicitly records `resolution_verified=false`.

The pipeline asserts disjoint exported component IDs. Tests also inspect the actual packet and retrieval exports, check ID uniqueness and test context exclusion. Semantic paraphrases below the heuristic threshold can remain, and the process is not author-disjoint. A customer may appear in different conversations.

## Human workflow and provenance

Start `scripts/label_batch.py`. It opens a local window with 20 messages per batch, the selected full customer message, available earlier context, intent/routing dropdowns and optional reason/notes/review fields. There are no suggested labels. Only intent and route are required to count a pair as labelled.

Every changed selection writes atomically to `annotations/golden-progress.json`; notes save after a short pause and are flushed before navigation or closing. Successful writes show Saved and the completed count. Write failures are explicit and prevent a false success message. Export backup saves a portable JSON copy; Restore backup validates the packet/version before replacing progress, retaining the prior file as `.bak`.

Run only one labelling window at a time. The first 50 examples are development data; remaining labels must not be inspected for prompt/threshold tuning. Per-example timestamps and source metadata record entry provenance. Optional fields left blank are missing labels, not inferred annotations. Reply quality labels and LLM-judge agreement will be collected separately.

## What the sampling does not establish

The representative subset represents a filtered population of replied-to Spotify conversations, not all incoming tweets or today's support traffic. Excluding duplicates, empty normalized texts and multi-brand threads changes prevalence. Challenge sampling deliberately changes case mix: report it separately, not as an unweighted single headline. Public DMs and account resolutions are not observed. Policy and UI statements from historical replies may be stale. This batch is not a completed golden set until a human labels it.

## Reproduce

From the repo directory, with Python 3.11+:

```sh
python scripts/prepare_batch.py --archive data/raw/twitter.zip
python -m unittest discover -s tests -v
python scripts/label_batch.py
```

Preparation refuses to overwrite an existing packet because doing so could invalidate human labels. Run in a fresh copy for reproduction. The source download script and archive checksum are documented in the README. No LLM API is required for preparation or annotation.
