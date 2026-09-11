"""Compatibility helpers for reply review; the runnable report is the Node script."""
from pathlib import Path
import subprocess


DIMS = ("correctness", "grounding", "usefulness", "routing_privacy")


def overall_pass(rating):
    values = [rating.get(name) for name in DIMS]
    return (
        all(value in (0, 1, 2) for value in values)
        and not rating.get("critical_failure", False)
        and 0 not in values
        and sum(values) >= 6
    )


def main():
    script = Path(__file__).with_suffix(".mjs")
    raise SystemExit(subprocess.run(["node", str(script)], check=False).returncode)


if __name__ == "__main__":
    main()
