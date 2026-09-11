"""Reapply the v3 deterministic gate to frozen v1 model outputs for diagnostics.

This uses already-inspected evaluation examples, so it must never be reported as a
held-out performance result.
"""
import json
from pathlib import Path

from run_gemini import STYLE_VERSION, gate
from support_system import Systems


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    packet = read(ROOT / "annotations/batch-200.json")
    gold = read(ROOT / "annotations/golden-completed.json")
    history = read(ROOT / "data/retrieval/history.json")
    frozen = read(ROOT / "results/gemini-3.5-final-v1/predictions.json")
    review = read(ROOT / "annotations/reply-review-packet-v2.json")
    review_key = read(ROOT / "results/reply-review-key-v2.json")
    human = read(ROOT / "annotations/reply-ratings-human-v2.json")["ratings"]

    examples = {row["tweet_id"]: row for row in packet["examples"]}
    predictions = {row["tweet_id"]: row for row in frozen}
    review_items = {row["rating_id"]: row for row in review["items"]}
    development = [row for row in packet["examples"] if row["split"] == "dev"]
    systems = Systems(development, {row["tweet_id"]: gold["labels"][row["tweet_id"]] for row in development}, history)

    rows = []
    for rating_id, identity in review_key.items():
        if identity["system"] != "gemini" or identity["partition"] != "validation":
            continue
        tweet_id = identity["tweet_id"]
        example = examples[tweet_id]
        prior = predictions[tweet_id]
        updated = gate(prior["raw_prediction"], example, systems.retrieve(example))
        old_item = review_items[rating_id]
        rows.append({
            "rating_id": rating_id,
            "tweet_id": tweet_id,
            "message": example["message"],
            "intent": updated["intent"],
            "old_draft": old_item["draft"],
            "new_draft": updated["draft"],
            "new_route": updated["route"],
            "draft_changed": old_item["draft"] != updated["draft"],
            "old_human_rating": human[rating_id],
            "new_human_rating": None,
        })

    old_critical = [row for row in rows if row["old_human_rating"]["critical_failure"]]
    output = {
        "style_version": STYLE_VERSION,
        "status": "post_evaluation_diagnostic_not_held_out",
        "warning": "These examples were used to design v3. Do not treat them as a new quality score; evaluate v3 on fresh untouched messages.",
        "summary": {
            "validation_examples": len(rows),
            "drafts_changed": sum(row["draft_changed"] for row in rows),
            "previously_critical_examples": len(old_critical),
            "previously_critical_drafts_changed": sum(row["draft_changed"] for row in old_critical),
        },
        "examples": rows,
    }
    path = ROOT / "results/posteval-v3-diagnostic.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
