import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_gemini import gate


class ExternalResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name("external_response_cases.json")
        cls.cases = json.loads(path.read_text(encoding="utf-8"))

    def test_fresh_adversarial_response_cases(self):
        self.assertEqual(len(self.cases), 20)
        for case in self.cases:
            with self.subTest(case=case["id"]):
                evidence = [{"support_tweet_id": "e1"}]
                raw = {
                    "intent": case["intent"],
                    "route": case["raw_route"],
                    "reason": "Fresh external guardrail scenario.",
                    "draft": case["raw_draft"],
                    "evidence_ids": case["evidence_ids"],
                    "reply_kind": "answer",
                }
                result = gate(raw, {"message": case["message"], "context_status": {}}, evidence)
                self.assertEqual(result["route"], case["expected_route"])
                lowered = result["draft"].casefold()
                for phrase in case["must_contain"]:
                    self.assertIn(phrase.casefold(), lowered)
                for phrase in case["must_not_contain"]:
                    self.assertNotIn(phrase.casefold(), lowered)


if __name__ == "__main__":
    unittest.main()
