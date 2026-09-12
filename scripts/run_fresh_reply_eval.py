"""Generate and freeze v3 Gemini replies for the untouched reply-review sample."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from gemini_client import Gemini
from run_gemini import INSTRUCTIONS, SCHEMA, STYLE_VERSION, gate, handoff_draft
from sentiment import analyze_sentiment, tone_guidance
from support_system import Systems, privacy_redact


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--fallback-model")
    parser.add_argument("--fallback-after", type=int)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--source", type=Path, default=ROOT / "annotations/fresh-reply-eval-v3-source.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/gemini-v3-fresh")
    args = parser.parse_args()
    if not 1 <= args.workers <= 3:
        raise ValueError("Use 1-3 workers.")

    source = read(args.source)
    batch = read(ROOT / "annotations/batch-200.json")
    gold = read(ROOT / "annotations/golden-completed.json")
    history = read(ROOT / "data/retrieval/history.json")
    development = [row for row in batch["examples"] if row["split"] == "dev"]
    systems = Systems(development, {row["tweet_id"]: gold["labels"][row["tweet_id"]] for row in development}, history)
    guide = (ROOT / "docs/annotation-guide.md").read_text(encoding="utf-8")
    instructions = INSTRUCTIONS + "\nGUIDE:\n" + guide
    manifest = {
        "source_packet_id": source["packet_id"], "model": args.model,
        "fallback_model": args.fallback_model, "fallback_after": args.fallback_after,
        "style_version": STYLE_VERSION,
        "prompt_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "Fresh post-fix reply evaluation. No labels or ratings existed when these outputs were generated.",
    }
    manifest_path = args.output / "manifest.json"
    if bool(args.fallback_model) != (args.fallback_after is not None):
        raise ValueError("Set both --fallback-model and --fallback-after, or neither.")
    if args.fallback_after is not None and not 0 <= args.fallback_after <= len(source["examples"]):
        raise ValueError("--fallback-after is outside the source packet.")
    if manifest_path.exists():
        prior = read(manifest_path)
        for key in ("source_packet_id", "model", "style_version", "prompt_sha256"):
            if prior.get(key) != manifest[key]:
                raise ValueError("Frozen run configuration changed; choose another output directory.")
        if (prior.get("fallback_model"), prior.get("fallback_after")) != (args.fallback_model, args.fallback_after):
            if (args.output / "predictions.json").exists():
                raise ValueError("A completed run cannot change its fallback model.")
            manifest["note"] += " The primary model hit quota after cached successes; the declared fallback generated only later packet positions."
            write(manifest_path, manifest)
    else:
        write(manifest_path, manifest)

    client = Gemini(args.model, args.key_file, args.output / "cache")
    fallback = Gemini(args.fallback_model, args.key_file, args.output / "cache") if args.fallback_model else None
    jobs = [(index, example, systems.retrieve(example)) for index, example in enumerate(source["examples"])]

    def generate(job):
        index, example, evidence = job
        sentiment = analyze_sentiment(example["message"])
        payload = {
            "message": privacy_redact(example["message"]),
            "context": [dict(item, text=privacy_redact(item["text"])) for item in example["context"][-4:]],
            "context_status": example["context_status"],
            "historical_records": [dict(item, customer_message=privacy_redact(item["customer_message"]), historical_reply=privacy_redact(item["historical_reply"])) for item in evidence],
            "sentiment_signal": sentiment, "tone_guidance": tone_guidance(sentiment),
        }
        try:
            active_client = fallback if fallback and index >= args.fallback_after else client
            raw, metadata = active_client.generate(instructions, payload, SCHEMA)
            result = gate(raw, example, evidence)
            error = None
        except Exception as exc:
            result = {"intent": "other_unclear", "route": "escalate", "reason": "Generation unavailable; human review required.",
                      "draft": handoff_draft(example, "other_unclear", "generation unavailable"), "evidence_ids": [],
                      "reply_kind": "handoff", "output_check_violations": ["generation unavailable"],
                      "style_adjustments": ["generation fallback"], "style_version": STYLE_VERSION, "sentiment": sentiment}
            metadata, error = None, str(exc)
        return {**result, "tweet_id": example["tweet_id"], "api_metadata": metadata, "api_error": error,
                "evidence": evidence}

    completed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(generate, job) for job in jobs]
        for index, future in enumerate(as_completed(futures), 1):
            completed.append(future.result())
            print(f"Generated {index}/{len(jobs)}", flush=True)
    order = {item["tweet_id"]: index for index, item in enumerate(source["examples"])}
    completed.sort(key=lambda item: order[item["tweet_id"]])
    if any(item["api_error"] for item in completed):
        write(args.output / "partial-predictions.json", completed)
        raise SystemExit(f"{sum(bool(item['api_error']) for item in completed)} calls failed; rerun to use the cache and retry.")
    write(args.output / "predictions.json", completed)

    examples = {item["tweet_id"]: item for item in source["examples"]}
    items = []
    for prediction in completed:
        example = examples[prediction["tweet_id"]]
        cited = set(prediction["evidence_ids"])
        evidence = [{key: row[key] for key in ("support_tweet_id", "customer_message", "historical_reply")}
                    for row in prediction["evidence"] if row["support_tweet_id"] in cited]
        rating_id = hashlib.sha256((source["packet_id"] + prediction["tweet_id"] + STYLE_VERSION).encode()).hexdigest()[:12]
        items.append({"rating_id": rating_id, "message": example["message"], "context": example["context"],
                      "route": prediction["route"], "draft": prediction["draft"], "evidence": evidence})
    packet_id = hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    write(ROOT / "annotations/fresh-reply-review-v3.json", {
        "packet_id": packet_id, "version": "fresh-reply-review-v3-v1", "style_version": STYLE_VERSION,
        "source_packet_id": source["packet_id"], "items": items,
    })
    print(json.dumps({"generated": len(items), "review_packet_id": packet_id}, indent=2))


if __name__ == "__main__":
    main()
