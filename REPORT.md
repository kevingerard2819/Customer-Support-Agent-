# Technical Evaluation Report: Spotify Customer Support Agent
**Hiver SDE Intern Take-Home Assignment**  
**Candidate:** kevingerard2819  
**Repository:** [https://github.com/kevingerard2819/Customer-Support-Agent-](https://github.com/kevingerard2819/Customer-Support-Agent-)  
**Evaluation Date:** September 2026  

---

## 1. Executive Summary

This report documents the design, implementation, and empirical evaluation of a conservative, safety-first automated customer support agent for **Spotify Support (`@SpotifyCares`)**, built on Kaggle's *Customer Support on Twitter* dataset (2.8+ million rows).

The system addresses customer inquiries by:
1. Classifying messages into one of 8 domain-specific intents.
2. Retrieving grounded historical support precedents from a component-disjoint knowledge base of 4,440 QA pairs.
3. Generating empathetic, cited responses using Google Gemini with dynamic auto-model fallback (`gemini-3.8-flash` $\to$ `3.7` $\to$ `3.6` $\to$ `3.5` $\to$ `2.5`).
4. Enforcing a strict, deterministic output safety gate that blocks hallucinations, unverified links, fake DM transfers, and refund/action promises.

### Key Headline Results:
* **Intent Macro-F1**: **`0.611`** on the 120-message representative test set (vs. **`0.191`** for Logistic Regression and **`0.049`** for the Trivial baseline).
* **Escalation Recall**: **`93.8%` (30/32)** of cases requiring human intervention were escalated safely.
* **Auto-Handling Coverage**: **`15.8%` (19/120)** of safe routine queries auto-handled without human intervention.
* **Human Reply Quality (Held-Out v3)**: **`100%` pass rate (30/30)** with **`0` critical failures** under a strict 4-dimension human rubric.
* **LLM-as-a-Judge Finding**: Empirically calibrated an automated LLM judge against human evaluations across 42 held-out pairs; the LLM judge exhibited poor agreement ($\kappa \in [0.14, 0.22]$) and **missed 100% of human critical failures (0/9)**, demonstrating why human calibration is essential for safety-critical customer support.

---

## 2. Problem Framing & Scope Boundaries

### 2.1. What "Good" Means for @SpotifyCares
For a high-volume consumer music streaming service:
1. **Conservatism Over Speculation**: The agent must never imply it accessed a customer's private account, processed a refund, or altered subscriptions.
2. **Empathetic Brand Voice**: Customer frustrations must be acknowledged with natural, calm language and contractions—not robotic corporate apologies.
3. **Strict Escalation Priority**: Financial disputes, security/hacking claims, repeated unresolved failures, and user distress must always route to human specialists.
4. **Auto-handling Definition**: `auto_handle` indicates that the **next public reply is completely safe to send without human review**; it does not claim end-to-end resolution of complex underlying backend cases.

### 2.2. What We Explicitly Chose NOT to Build
* **No Direct Account/Payment Integrations**: We do not simulate or claim backend database mutations.
* **No Inferred Media Handling**: Inaccessible screenshots or external URLs are treated as missing context rather than guessed.
* **No Policy Hallucinations**: Old historical tweets are treated as precedent patterns, not ground-truth current Spotify legal policy.

---

## 3. Data Engineering & Golden Evaluation Set

### 3.1. Leakage Prevention via Connected Components
Twitter support threads frequently contain multiple exchanges. Random row-level splitting causes catastrophic data leakage where later turns of a conversation leak into retrieval or training.
* **Component Graph**: We constructed undirected connected component graphs across 2.8M rows, clustering 28,280 Spotify conversation components.
* **Disjoint Retrieval Corpus**: 4,440 historical customer/reply pairs were extracted from 3,000 components **completely isolated** from all evaluation and discovery data.

### 3.2. Golden Evaluation Set (200 Hand-Labelled Examples)
The candidate personally annotated 200 messages using an autosaving local GUI tool with no AI pre-suggestions:
* **Development Split (50 messages)**: Used to fit TF-IDF vectorizers and baselines.
* **Representative Test Split (120 messages)**: Sampled randomly from eligible components to evaluate production performance.
* **Challenge Test Split (30 messages)**: Enriched with adversarial inputs, repeated failures, short follow-ups, and distress signals.

```
Taxonomy (8 Intents):
1. billing_subscription     5. catalog_availability
2. account_access_security  6. feedback_feature_request
3. playback_app             7. social_acknowledgement
4. library_playlists        8. other_unclear
```

---

## 4. System Architecture & Safety Gate

```
Customer Message
       │
       ▼
[ Privacy Redaction & Cleaning ] (Masks emails, phone numbers, cards)
       │
       ├──► [ TF-IDF Precedent Retrieval ] (Top-3 historical pairs from 4,440 corpus)
       ├──► [ Deterministic Sentiment Signal ] (Positive / Negative / Neutral / Mixed / Distressed)
       │
       ▼
[ Gemini 3.5/3.8 Flash Client with Auto-Fallback ] (Strict JSON Schema)
       │
       ▼
[ Deterministic Safety Gate ]
  ├─ Validates evidence citation IDs
  ├─ Blocks prohibited action claims (refunds, cancellations, fake DMs)
  ├─ Catches sensitive safety triggers (self-harm distress, account security)
  └─ Injects intent-tailored empathetic handoffs
       │
       ▼
Final Public Reply (auto_handle or escalate)
```

---

## 5. Experimental Results vs. Baselines

### 5.1. Classification & Routing Results (120-Message Representative Test)

| System | Intent Macro-F1 (All 8 Classes) | Auto Coverage | Escalation Recall | Auto-Route Disagreements |
|---|---:|---:|---:|---:|
| **Always Escalate (Trivial Baseline)** | 0.049 | 0.0% (0/120) | 100.0% | 0/0 (N/A) |
| **TF-IDF + Logistic Regression** | 0.191 | 22.5% (27/120) | 78.1% | 7/27 (25.9%) |
| **Guarded Retrieval Templates** | 0.191 | 2.5% (3/120) | 100.0% | 0/3 (0.0%) |
| **Gemini 3.5 Flash + Output Gate** | **0.611** | **15.8% (19/120)** | **93.8% (30/32)** | **2/19 (10.5%)** |

*On the 30-message challenge set, Gemini achieved 0.499 macro-F1, auto-handled 1/30 cases, and caught 100% (6/6) of required escalations.*

---

## 6. Blinded Human Reply Review & LLM-as-a-Judge Calibration

### 6.1. Blinded Human Quality Review (90 Outputs)
A blinded study evaluated 90 outputs across 4 dimensions (0–2 score): Correctness, Grounding, Usefulness, Routing/Privacy.

| System (Held-Out Human Review) | Pass Rate | Critical Failures | Mean Correctness | Mean Grounding | Mean Usefulness | Mean Routing/Privacy |
|---|---:|---:|---:|---:|---:|---:|
| **Trivial Handoff** | 60% (12/20) | 25% (5/20) | 1.40 | 1.40 | 1.50 | 1.55 |
| **Simple Guarded Templates** | **80% (16/20)** | 20% (4/20) | **1.55** | **1.55** | 1.50 | **1.80** |
| **Gemini + Gate (`human-tone-v2`)** | 75% (15/20) | 20% (4/20) | 1.50 | 1.50 | **1.55** | 1.70 |
| **Post-Fix Gemini (`v3-fresh`)** | **100% (30/30)** | **0% (0/30)** | **1.93** | **2.00** | **1.97** | **2.00** |

### 6.2. LLM-as-a-Judge Empirical Analysis
We evaluated Gemini as an automated evaluator against human ground-truth ratings across 42 held-out pairs:
* **Low Inter-Rater Reliability**: Linear-weighted Kappa was only **0.142–0.222** across dimensions.
* **Severe False-Acceptance Flaw**: The LLM judge **missed 9 out of 9 human-flagged critical failures (0% recall)**.
* **Conclusion**: Automated LLM judges cannot replace rigorous human-in-the-loop review for high-risk customer support guardrails.

---

## 7. Failure Analysis: Top 5 Failure Modes

### Mode 1: Product Requests Overlapping with Broken Behavior
* **Examples**: Tweet `2746365` (*"why spotify on ios is acting weird??"* - gold: `feedback_feature_request`, pred: `playback_app`); Tweet `31593` (*asking for an artist dislike button* - gold: `feedback_feature_request`, pred: `other_unclear`).
* **Hypothesis**: Short user queries simultaneously express frustration and desired features. Single-label taxonomies force arbitrary tie-breaks.

### Mode 2: Unstable Taxonomy Boundaries (Library vs. Catalog vs. Playback)
* **Examples**: Tweet `2216049` (*asking to add an artist's OST* - gold: `library_playlists`, pred: `catalog_availability`); Tweet `2442061` (*playlist plays wrong version on desktop* - gold: `library_playlists`, pred: `playback_app`).
* **Hypothesis**: The mentioned noun (*playlist*) competes with the root cause (*missing license* or *app glitch*). Prompt needs explicit operational definitions.

### Mode 3: Plausible Retrieved Explanations Causing Unsafe Auto-Routes
* **Examples**: Tweet `1695256` (*complaining ad-free timer expired early* - auto-replied with invented app-crash reset theory); Tweet `1286621` (*missing presale code* - auto-replied with generic explanation). Both were gold `escalate`.
* **Hypothesis**: Plausible-sounding historical explanations trick the model into asserting verified causal facts. Safety gate must enforce strict citation entailment for promotional benefits.

### Mode 4: Output Gate Cutting Valid Coverage
* **Examples**: Tweet `834634` (*playlist followers query*); Tweet `2580777` (*recommendation query*). The gate caught 74 unverified raw claims and converted them to escalations.
* **Hypothesis**: Broad regexes prevent hallucinations but over-penalize harmless general advice. An allowlist of official Spotify help articles is needed to recover coverage safely.

### Mode 5: Generic Handoffs Damaging Perceived Relevance
* **Examples**: Tweets `2305413` (Apple Watch app), `576784` (watch volume), and `1659439` (bring back lyrics) received identical account-style private DM handoffs in v2. Human reviewers gave all three **critical failure** ratings for total irrelevance.
* **Fix & Verification (v3/v4)**: Developed intent-tailored handoffs (e.g., feature suggestions acknowledge the idea without promising releases). In the fresh 30-item v3 validation, pass rate rose to **100% (30/30) with 0 critical failures**.

---

## 8. "What is Misleading About My Headline Number?"

1. **`0.611` Macro-F1 Is Not Reply Quality**: A correctly classified intent can still produce a hallucinated, unhelpful, or unsafe response.
2. **`2/19` Disagreement Rate Has Wide Confidence Intervals**: The Wilson 95% interval for 2/19 is `[2.9%, 31.4%]`. 120 messages are insufficient for production safety claims.
3. **Always-Escalate Appears Artificially Safe**: A 100% escalation recall provides zero automated value to the business.
4. **Filtered Distribution**: Covers single-brand, English, replied-to tweets from 2017; it does not capture present-day multi-channel conversational volume.
5. **Challenge Set Is Artificially Skewed**: Intentionally saturated with short, hostile, or sensitive queries.
6. **Single-Annotator Label Noise**: Taxonomy boundary ambiguity reflects single-reviewer judgment; no multi-human kappa is claimed.
7. **Historical Replies Are Not Gold Resolutions**: Public tweets frequently contain outdated links or redirect to DMs.
8. **Gate Trades Usefulness for Conservatism**: Final coverage reflects strict regex rules rather than nuanced language comprehension.
9. **The LLM Did Not Outperform Simple Baselines in v2**: On initial held-out human review, simple templates achieved 80% vs 75% for Gemini.
10. **Automated LLM Judges Are Unreliable**: Gemini-as-a-judge missed all 9 critical human errors.
11. **30/30 Post-Fix Pass Rate Is Candidate-Only**: Evaluated by a single reviewer on a small candidate sample without concurrent baseline controls.
12. **Model Version Drift**: Provider quota exhaustion required mixing Gemini 3.5 and 3.8 outputs.

---

## 9. Decision Log (15 Non-Obvious Decisions)

1. **Choose SpotifyCares**: Rich mix of software bugs, general usability, and account escalations.
2. **Direct Twitter Source**: Retained original tweet IDs and archive checksum for complete traceability.
3. **Exclude Raw Archive from Repo**: Kept the 177MB raw zip out of git; committed clean, reproducible artifacts.
4. **Deterministic Reservoir Sampling**: Avoided first-row bias while keeping memory footprints negligible.
5. **Eight Provisional Intents**: Sufficient granularity without starving classes in a 200-item dataset.
6. **Decouple Intent from Routing**: Safety/account risks can occur within any intent category.
7. **Define Auto-Handling at Next-Reply Level**: Auto-handling guarantees safe public messaging, not backend resolution.
8. **Never Treat Historical Replies as Gold Truth**: Prevented the agent from copying stale policies or private DM claims.
9. **No-AI-Assistance Human Annotation**: Built a local GUI tool to prevent accidental model pre-labeling bias.
10. **12-Example Pilot Before Full Annotation**: Caught taxonomy ambiguities before committing to 200 items.
11. **Graph-Based Component Exclusion**: Prevented cross-split conversational data leakage.
12. **Deduplicate Before Splitting**: Prevented paraphrased repeats from inflating retrieval scores.
13. **Retain Incomplete & Hostile Messages in Test Set**: Messy real-world context is an evaluation requirement, not noise.
14. **Cached Reproduction Path**: Engineered `reproduce_cached.py` to run in 0.07s without API keys or network latency.
15. **Intent-Specific Graceful Handoffs**: Replaced generic error messages with empathetic, category-specific handoffs.

---

## 10. What We Would Do Next With One More Week

1. **Multi-Annotator Inter-Rater Reliability**: Have a second annotator label 60 stratified examples to compute Cohen’s $\kappa$ and adjudicate boundary disagreements.
2. **NLI-Based Grounding Gate**: Replace regex checks with a Natural Language Inference (NLI) cross-encoder to verify that every draft sentence is strictly entailed by historical evidence spans.
3. **Official Help Center URL Allowlist**: Integrate verified official Spotify support article URLs (`support.spotify.com/article/...`).
4. **Cross-Family LLM-as-a-Judge**: Re-evaluate with Claude 3.5 Sonnet or GPT-4o to eliminate intra-family evaluation bias.
5. **Scale Evaluation Corpus**: Expand the golden set to 500+ items, incorporating multilingual tweets and recent temporal slices.

---

## 11. Quick Reproduction Commands

From the repository root (`outputs/hiver-support-agent/`):

```bash
# 1. Install minimal dependencies
python -m pip install -r requirements.txt

# 2. Recalculate all headline metrics from cached predictions (0.07s, zero network calls)
python scripts/reproduce_cached.py

# 3. Run full test suite (27 unit & adversarial tests)
python -m unittest discover -s tests -v

# 4. Generate reply review reports
node scripts/report_reply_review.mjs
python scripts/report_fresh_reply_review.py

# 5. Launch interactive live demo UI
python scripts/try_live_agent.py --port 8766
# Open http://127.0.0.1:8766 in your browser
```
