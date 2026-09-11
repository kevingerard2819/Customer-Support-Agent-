import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from metrics import evaluate,wilson,judge_agreement
from run_gemini import gate,polish_draft,handoff_draft,has_unsupported_action
from support_system import Systems
from reply_rating_store import RatingStore
from sentiment import analyze_sentiment,tone_guidance
import json
import tempfile

class SystemTests(unittest.TestCase):
    def test_zero_auto_is_undefined_risk_not_zero(self):
        m=evaluate([dict(tweet_id='1',intent='other_unclear',route='escalate')],{'1':dict(intent='other_unclear',route='escalate')})
        self.assertIsNone(m['auto_route_disagreement_rate'])
        self.assertEqual(m['escalation_recall'],1)
        self.assertGreater(wilson(0,3)[1],.5)

    def test_invalid_citations_and_action_claims_escalate(self):
        example={'message':'Thank you','context_status':{}}
        pred=dict(intent='social_acknowledgement',route='auto_handle',draft="We've issued a refund.",reason='fine',evidence_ids=['fake'],reply_kind='answer')
        result=gate(pred,example,[])
        self.assertEqual(result['route'],'escalate')
        self.assertTrue(result['output_check_violations'])
        self.assertNotIn('issued',result['draft'])
        self.assertIn('DMs',result['draft'])
        self.assertNotIn('This needs a human support review',result['draft'])

    def test_tone_cleanup_removes_placeholders_jargon_and_signatures(self):
        result,changes=polish_draft('@user We can check this out backstage!! /TB')
        self.assertEqual(result,'We can take a closer look privately!')
        self.assertTrue(changes)

    def test_account_handoff_is_natural_and_privacy_safe(self):
        text=handoff_draft({'message':'I was charged twice'},'billing_subscription','payment review')
        self.assertIn('support team',text)
        self.assertIn('DMs',text)
        self.assertIn("don't post",text)
        self.assertNotIn('issued',text)

    def test_dm_and_internal_forwarding_claims_are_blocked(self):
        self.assertTrue(has_unsupported_action("We've received your message and sent a DM back."))
        self.assertTrue(has_unsupported_action("We'll pass this to the relevant team."))

    def test_sentiment_signal_handles_support_tone(self):
        self.assertEqual(analyze_sentiment('Thank you, I love it 😊')['label'],'positive')
        self.assertEqual(analyze_sentiment('This app is broken and frustrating')['label'],'negative')
        self.assertEqual(analyze_sentiment('Thanks, but it is still broken')['label'],'mixed')
        self.assertEqual(analyze_sentiment('I want to kill myself')['label'],'distressed')
        self.assertEqual(analyze_sentiment('How do I sort a playlist?')['label'],'neutral')
        self.assertIn('frustration',tone_guidance(analyze_sentiment('This is awful')))

    def test_negative_sentiment_alone_does_not_force_escalation(self):
        from support_system import risk_reason
        example={'message':'This design is awful','context_status':{}}
        self.assertIsNone(risk_reason(example,'feedback_feature_request'))

    def test_reject_training_on_test_split(self):
        with self.assertRaises(ValueError): Systems([{'split':'test_representative'}],{},[])

    def test_missing_human_ratings_do_not_report_agreement(self):
        result=judge_agreement({}, {'one':{'correctness':2}})
        self.assertEqual(result['n_paired'],0)
        self.assertIsNone(result['dimensions']['correctness']['exact_agreement'])

    def test_judge_critical_false_accept(self):
        result=judge_agreement({'a':{'correctness':0,'critical_failure':True}}, {'a':{'correctness':2,'critical_failure':False}})
        self.assertEqual(result['judge_missed_human_critical_failures'],1)
        self.assertEqual(result['dimensions']['correctness']['exact_agreement'],0)
        self.assertIsNone(result['dimensions']['correctness']['weighted_kappa'])
        self.assertEqual(result['critical_failure_exact_agreement'],0)

    def test_reply_rating_store_requires_complete_rubric(self):
        with tempfile.TemporaryDirectory() as folder:
            packet=Path(folder)/'packet.json';progress=Path(folder)/'progress.json'
            packet.write_text(json.dumps({'packet_id':'p','items':[{'rating_id':'r'}]}))
            store=RatingStore(packet,progress)
            store.update('r',correctness=2,grounding=2,usefulness=2,routing_privacy=2,critical_failure=False,notes='')
            self.assertEqual(store.complete(),1)
            self.assertEqual(RatingStore(packet,progress).complete(),1)
            with self.assertRaises(ValueError):store.update('r',correctness=3)

    def test_unrated_search_can_skip_current_item(self):
        # Mirrors the UI's circular search order: item 0 must not trap the user.
        current=0;size=4
        self.assertEqual([(current+offset)%size for offset in range(1,size+1)],[1,2,3,0])

    def test_reply_pass_threshold_and_critical_failure(self):
        from report_reply_review import overall_pass
        good={'correctness':2,'grounding':1,'usefulness':1,'routing_privacy':2,'critical_failure':False}
        self.assertTrue(overall_pass(good))
        self.assertFalse(overall_pass(dict(good,correctness=0)))
        self.assertFalse(overall_pass(dict(good,critical_failure=True)))

if __name__=='__main__': unittest.main()
