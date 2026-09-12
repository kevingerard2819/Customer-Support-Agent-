"""Freeze an untouched, component-disjoint sample for v3 reply review."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random

from inspect_data import rows
from prepare_batch import Components, SimilarityIndex, normalized, prior_context, timestamp


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260912)
    parser.add_argument("--output", type=Path, default=ROOT / "annotations/fresh-reply-eval-v3-source.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Fresh v3 source packet already exists; refusing to replace it.")
    if not 20 <= args.count <= 60:
        raise ValueError("Use 20-60 fresh examples.")

    graph = Components()
    spotify_reply_ids = []
    print("Pass 1/2: reconstructing conversation components...", flush=True)
    for row in rows(args.archive):
        tweet_id = int(row["tweet_id"])
        graph.ensure(tweet_id)
        for link in row["response_tweet_id"].split(",") + [row["in_response_to_tweet_id"]]:
            if link.strip():
                graph.union(tweet_id, int(link.strip()))
        if row["inbound"].lower() == "false" and row["author_id"] == "SpotifyCares":
            spotify_reply_ids.append(tweet_id)
    spotify_components = {graph.find(tweet_id) for tweet_id in spotify_reply_ids}

    batch = read(ROOT / "annotations/batch-200.json")
    history = read(ROOT / "data/retrieval/history.json")
    excluded = {int(item["component_id"]) for item in batch["examples"]}
    excluded.update(int(item["component_id"]) for item in history)
    for path in (ROOT / "data/discovery").glob("*.json"):
        if path.name == "profile.json":
            continue
        for pair in read(path):
            excluded.update(graph.find(int(pair[role]["tweet_id"])) for role in ("customer", "support"))

    indexed = {}
    component_rows = defaultdict(list)
    multi_brand = set()
    print("Pass 2/2: collecting untouched Spotify conversations...", flush=True)
    for row in rows(args.archive):
        component = graph.find(int(row["tweet_id"]))
        if component not in spotify_components:
            continue
        indexed[row["tweet_id"]] = row
        component_rows[component].append(row)
        if row["inbound"].lower() == "false" and row["author_id"] != "SpotifyCares":
            multi_brand.add(component)
    excluded.update(multi_brand)

    candidates = defaultdict(set)
    for row in indexed.values():
        if row["inbound"].lower() != "false" or row["author_id"] != "SpotifyCares":
            continue
        customer = indexed.get(row["in_response_to_tweet_id"])
        component = graph.find(int(row["tweet_id"]))
        if component in excluded or not customer or customer["inbound"].lower() != "true":
            continue
        if len(normalized(customer["text"]).split()) >= 4:
            candidates[component].add(customer["tweet_id"])

    overlap = SimilarityIndex()
    for example in batch["examples"]:
        overlap.add(example["message"])
    for item in history:
        overlap.add(item["customer_message"])
    for path in (ROOT / "data/discovery").glob("*.json"):
        if path.name != "profile.json":
            for pair in read(path):
                overlap.add(pair["customer"]["text"])

    rng = random.Random(args.seed)
    component_ids = sorted(candidates)
    rng.shuffle(component_ids)
    selected = []
    for component in component_ids:
        choices = sorted(candidates[component], key=int)
        row = indexed[rng.choice(choices)]
        if overlap.similar(row["text"]):
            continue
        context, context_status = prior_context(row, indexed)
        selected.append({
            "tweet_id": row["tweet_id"], "component_id": str(component),
            "message": row["text"], "created_at": row["created_at"],
            "context": context, "context_status": context_status,
        })
        overlap.add(row["text"])
        if len(selected) == args.count:
            break
    if len(selected) != args.count:
        raise ValueError(f"Only found {len(selected)} eligible fresh examples")

    digest = hashlib.sha256(json.dumps(selected, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    write(args.output, {
        "packet_id": digest, "version": "fresh-reply-eval-v3-source-v1",
        "seed": args.seed, "count": len(selected),
        "sampling": "Random eligible Spotify conversation components after excluding discovery, all 200 labelled components, all retrieval components, multi-brand threads, and near-duplicates. One directly answered customer message per component.",
        "examples": selected,
    })
    print(json.dumps({"output": str(args.output), "packet_id": digest, "count": len(selected)}, indent=2))


if __name__ == "__main__":
    main()
