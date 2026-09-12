"""Summarize the independent human ratings for the fresh v3 reply sample."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIMS = ("correctness", "grounding", "usefulness", "routing_privacy")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    packet = read(ROOT / "annotations/fresh-reply-review-v3.json")
    ratings = read(ROOT / "annotations/fresh-reply-ratings-human-v3.json")
    if ratings.get("packet_id") != packet["packet_id"]:
        raise ValueError("Rating packet mismatch")
    complete = {key: value for key, value in ratings.get("ratings", {}).items()
                if all(value.get(dim) in (0, 1, 2) for dim in DIMS)
                and isinstance(value.get("critical_failure"), bool)}
    if len(complete) != len(packet["items"]):
        raise SystemExit(f"Ratings are incomplete: {len(complete)}/{len(packet['items'])}")
    passed = {key: not value["critical_failure"] and all(value[dim] > 0 for dim in DIMS)
              and sum(value[dim] for dim in DIMS) >= 6 for key, value in complete.items()}
    report = {
        "packet_id": packet["packet_id"], "n": len(complete),
        "pass_count": sum(passed.values()), "pass_rate": sum(passed.values()) / len(passed),
        "critical_failure_count": sum(value["critical_failure"] for value in complete.values()),
        "dimension_means": {dim: sum(value[dim] for value in complete.values()) / len(complete) for dim in DIMS},
        "failed_rating_ids": [key for key, value in passed.items() if not value],
        "definition": "Pass requires no critical failure, no zero dimension, and at least 6/8 total.",
        "limitation": "Post-fix reply-quality sample only; it has no independently labelled intent ground truth. The run used Gemini 3.5 for 19 items and Gemini 3.8 for 11 after provider quota was reached.",
    }
    output = ROOT / "results/fresh-reply-review-v3-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
