"""Replay the frozen v3 raw outputs through v4 without assigning new scores."""
import json
from pathlib import Path

from run_gemini import STYLE_VERSION, gate


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    source = read(ROOT / "annotations/fresh-reply-eval-v3-source.json")
    predictions = read(ROOT / "results/gemini-v3-fresh/predictions.json")
    examples = {item["tweet_id"]: item for item in source["examples"]}
    changes = []
    for old in predictions:
        cache_path = ROOT / "results/gemini-v3-fresh/cache" / (old["api_metadata"]["request_sha256"] + ".json")
        raw = read(cache_path)["parsed"]
        new = gate(raw, examples[old["tweet_id"]], old["evidence"])
        if new["draft"] != old["draft"] or new["route"] != old["route"]:
            changes.append({"tweet_id": old["tweet_id"], "message": examples[old["tweet_id"]]["message"],
                            "old_route": old["route"], "old_draft": old["draft"],
                            "new_route": new["route"], "new_draft": new["draft"],
                            "new_violations": new["output_check_violations"]})
    output = {
        "source_packet_id": source["packet_id"], "style_version": STYLE_VERSION,
        "changed_count": len(changes), "changes": changes,
        "evaluation_status": "post-evaluation diagnostic only",
        "note": "The v3 human ratings were completed before these changes. Old ratings are not transferred to v4.",
    }
    path = ROOT / "results/posteval-v4-diagnostic.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"changed_count": len(changes), "output": str(path)}, indent=2))


if __name__ == "__main__":
    main()
