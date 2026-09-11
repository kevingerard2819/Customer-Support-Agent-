# Discovery checkpoint

## Source and method

Original source: [Customer Support on Twitter, Thought Vector](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter). Downloaded 2026-09-09 via Kaggle's public dataset endpoint. Dataset card lists CC BY-NC-SA 4.0. The included samples are dataset excerpts under that source license, not newly authored training examples. No third-party implementation was borrowed.

The downloaded archive contains **2,811,774 rows**. Its SHA-256 and complete per-brand support counts are saved in `data/discovery/profile.json`. Sampling uses seed 42 and reservoir sampling of 120 support tweets with parent IDs per shortlisted brand, followed by a second pass to resolve the parents. This overweights conversations with multiple brand replies and excludes unanswered customer messages. It is exploratory, not a prevalence estimate or evaluation split.

| Brand | All outbound support tweets | Valid inbound-parent pairs in 120 sampled replies |
|---|---:|---:|
| SpotifyCares | 43,265 | 120 |
| XboxSupport | 24,557 | 115 |
| AppleSupport | 106,860 | 119 |
| AmazonHelp | 169,840 | 119 |

## Choice: SpotifyCares

AI-assisted qualitative review covered all 120 Spotify pairs and the first 12 valid pairs for each alternative. This was not a human labelling exercise or exhaustive comparative study. Spotify offers recurring consumer software issues, substantial data, and a useful mixture of general help and account-dependent escalation. The alternative samples include hardware/version dependencies (Xbox/Apple) and multilingual order/account workflows (Amazon). These observations motivate the choice; they do not establish quantitative superiority.

## Concrete observations

The following IDs refer to customer tweets in the supplied Spotify discovery file. These are paraphrases and proposed interpretations, not human gold labels.

| Tweet ID | Observation | Design consequence |
|---|---|---|
| 1500094 | Customer reports being charged three times; support moves to DM | Classify billing, escalate account investigation; no invented refund |
| 602845 | Reinstall already failed for a desktop launch error; support requests OS version | Preserve prior attempts; a generic reinstall answer is not useful |
| 1909997 | Controls stopped working after an update; support suggests restart/login steps | A source for historical troubleshooting, not a guaranteed fix |
| 2728389 | Password reset email does not arrive, including spam folder | Account access and failed recovery need human help |
| 2313472 | Family invitation cannot be accepted | Billing/entitlement boundary needs clear guidance |
| 2251335 | Customer asks how to sort a playlist | General help candidate; do not invent UI steps from a link-only source |
| 57576 | Historic reply treats blocking people as a feature idea | Old replies cannot establish present-day capability |
| 1016527 | Historic country launch question | Do not reuse old country-availability claims as current facts |
| 2076929 | Message only says “bump” | Need preceding context; the future reply cannot supply the intent |
| 1101774 | Billing complaint includes masked email and an account identifier | Avoid repeating private identifiers in a generated reply |
| 832174 | Music request includes a reference to past suicidal distress | Primary intent alone is insufficient for routing |
| 1726752 | Thanks appears alongside unresolved dissatisfaction | Do not classify solely from the word “thanks” |

Public replies frequently redirect to DM or claim a DM/internal follow-up happened. The data does not expose that private resolution. Retrieval must not convert these into claims that the assistant has sent messages or contacted a team. Some responses are numbered fragments; reconstruction must account for incomplete support turns.

## Next experiment

Human-complete the 12-example pilot without viewing its historical replies. Revise boundaries based on ambiguity. Then reconstruct connected threads, exclude all discovery-connected components from scored test data, deduplicate before splitting, and sample 200 independent examples (50 development, 150 held-out). Keep random and deliberately selected challenge portions distinct. Freeze the test labels before tuning thresholds. No headline results exist yet.
