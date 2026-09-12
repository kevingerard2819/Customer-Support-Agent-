import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FreshReplyEvalTests(unittest.TestCase):
    def test_fresh_source_is_component_disjoint(self):
        fresh = json.loads((ROOT / "annotations/fresh-reply-eval-v3-source.json").read_text(encoding="utf-8"))
        batch = json.loads((ROOT / "annotations/batch-200.json").read_text(encoding="utf-8"))
        history = json.loads((ROOT / "data/retrieval/history.json").read_text(encoding="utf-8"))
        fresh_components = {item["component_id"] for item in fresh["examples"]}
        self.assertEqual(len(fresh["examples"]), 30)
        self.assertEqual(len(fresh_components), 30)
        self.assertTrue(fresh_components.isdisjoint(item["component_id"] for item in batch["examples"]))
        self.assertTrue(fresh_components.isdisjoint(item["component_id"] for item in history))

    def test_frozen_predictions_match_review_packet(self):
        source = json.loads((ROOT / "annotations/fresh-reply-eval-v3-source.json").read_text(encoding="utf-8"))
        predictions = json.loads((ROOT / "results/gemini-v3-fresh/predictions.json").read_text(encoding="utf-8"))
        review = json.loads((ROOT / "annotations/fresh-reply-review-v3.json").read_text(encoding="utf-8"))
        source_ids = [item["tweet_id"] for item in source["examples"]]
        self.assertEqual([item["tweet_id"] for item in predictions], source_ids)
        self.assertTrue(all(not item["api_error"] for item in predictions))
        self.assertEqual(len(review["items"]), 30)
        self.assertEqual(len({item["rating_id"] for item in review["items"]}), 30)


if __name__ == "__main__":
    unittest.main()
