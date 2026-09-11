"""Recompute headline metrics from committed cached predictions without API calls."""
import json
from pathlib import Path
import time

from metrics import evaluate


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    gold = read(root / "annotations/golden-completed.json")["labels"]
    offline = read(root / "results/offline-v1/predictions.json")
    gemini = read(root / "results/gemini-3.5-final-v1/predictions.json")
    rows = {}
    for system in ("trivial", "simple", "guarded_retrieval"):
        rows[system] = {
            split: evaluate([p for p in offline if p["system"] == system and p["split"] == split], gold)
            for split in ("dev", "test_representative", "test_challenge")
        }
    rows["gemini"] = {
        split: evaluate([p for p in gemini if p["split"] == split], gold)
        for split in ("dev", "test_representative", "test_challenge")
    }
    out = {
        "runtime_seconds": time.perf_counter() - started,
        "systems": rows,
        "note": "Computed from committed cached predictions; this command makes no network or API calls.",
    }
    destination = root / "results/reproduced-metrics.json"
    destination.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "runtime_seconds": out["runtime_seconds"],
        "test_representative": {name: values["test_representative"] for name, values in rows.items()},
    }, indent=2))


if __name__ == "__main__":
    main()
