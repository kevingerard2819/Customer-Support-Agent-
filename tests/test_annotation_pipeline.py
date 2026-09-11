import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from annotation_store import Store
from prepare_batch import Components, SimilarityIndex, prior_context


class PipelineTests(unittest.TestCase):
    def test_components_include_missing_shared_parent(self):
        c=Components()
        c.union(10,999)
        c.union(20,999)
        c.union(30,40)
        self.assertEqual(c.find(10),c.find(20))
        self.assertNotEqual(c.find(10),c.find(40))

    def test_duplicate_normalization_and_short_message(self):
        index=SimilarityIndex()
        index.add('@person Thanks! https://t.co/a')
        self.assertTrue(index.similar('@other thanks'))
        self.assertFalse(index.similar('I cannot log into my account'))
        index.add('My app keeps crashing when I open the playlist on my phone')
        self.assertTrue(index.similar('@SpotifyCares My app keeps crashing when I open the playlist on my phone!'))

    def test_context_excludes_later_messages(self):
        def row(i,parent,time):
            return dict(tweet_id=i,in_response_to_tweet_id=parent,created_at=f'Tue Nov 07 {time} +0000 2017',text=i,inbound='True')
        indexed={'1':row('1','','10:00:00'),'2':row('2','1','11:00:00'),'3':row('3','2','12:00:00')}
        context,flags=prior_context(indexed['2'],indexed)
        self.assertEqual([r['tweet_id'] for r in context],['1'])
        self.assertFalse(any(flags.values()))
        indexed['1']['created_at']='Tue Nov 07 13:00:00 +0000 2017'
        context,flags=prior_context(indexed['2'],indexed)
        self.assertEqual(context,[])
        self.assertTrue(flags['timestamp_conflict'])

    def test_saved_progress_survives_restart_and_export(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            packet=folder/'packet.json'
            packet.write_text(json.dumps({'packet_id':'abc','guide_version':'0.2','examples':[{'tweet_id':'1'}]}))
            store=Store(packet,folder/'labels.json')
            self.assertEqual(store.complete(),0)
            store.update('1',intent='billing_subscription')
            self.assertEqual(store.complete(),0)
            store.update('1',route='escalate',notes='Human review needed')
            restarted=Store(packet,folder/'labels.json')
            self.assertEqual(restarted.complete(),1)
            restarted.export(folder/'backup.json')
            self.assertEqual(json.loads((folder/'backup.json').read_text()),restarted.data)
            before=restarted.data
            with patch('annotation_store.os.replace',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): restarted.update('1',route='auto_handle')
            self.assertEqual(Store(packet,folder/'labels.json').data,before)
            self.assertEqual(restarted.data,before)
            with self.assertRaises(ValueError): restarted.update('unknown',route='escalate')
            bad=dict(before,packet_id='other')
            (folder/'wrong.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError): restarted.restore(folder/'wrong.json')

    def test_real_packet_split_and_input_integrity(self):
        root=Path(__file__).resolve().parents[1]
        packet=json.loads((root/'annotations/batch-200.json').read_text(encoding='utf-8'))
        history=json.loads((root/'data/retrieval/history.json').read_text(encoding='utf-8'))
        examples=packet['examples']
        self.assertEqual(len(examples),200)
        self.assertEqual(len({e['component_id'] for e in examples}),200)
        self.assertFalse({e['component_id'] for e in examples}&{e['component_id'] for e in history})
        for e in examples:
            self.assertNotIn('historical_reply',e)
            self.assertNotIn(e['tweet_id'],{c['tweet_id'] for c in e['context']})


if __name__=='__main__': unittest.main()
