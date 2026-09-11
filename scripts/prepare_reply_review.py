"""Freeze 90 blinded outputs: trivial/simple/Gemini on the same 30 inputs."""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'annotations/reply-review-packet.json'
    if out.exists(): raise SystemExit('Reply packet exists; refusing to invalidate ratings.')
    examples=json.loads((ROOT/'annotations/batch-200.json').read_text(encoding='utf-8'))['examples']
    history=json.loads((ROOT/'data/retrieval/history.json').read_text(encoding='utf-8'))
    hist={h['support_tweet_id']:h for h in history}
    predictions=json.loads((ROOT/'results/offline-v1/predictions.json').read_text(encoding='utf-8'))+json.loads((ROOT/'results/gemini-3.5-final-v1/predictions.json').read_text(encoding='utf-8'))
    index={(p['system'],p['tweet_id']):p for p in predictions}
    rng=random.Random(778)
    selected=rng.sample([e for e in examples if e['split']=='dev'],10)+rng.sample([e for e in examples if e['split']=='test_representative'],20)
    items=[];key={}
    for e in selected:
        for system in ('trivial','simple','gemini'):
            p=index[system,e['tweet_id']]
            rid=hashlib.sha256((system+e['tweet_id']+'final-rating-v1').encode()).hexdigest()[:12]
            key[rid]={'system':system,'tweet_id':e['tweet_id'],'partition':'calibration' if e['split']=='dev' else 'validation'}
            items.append({'rating_id':rid,'message':e['message'],'context':e['context'][-4:],
                          'draft':p['draft'],'route':p['route'],
                          'evidence':[hist[i] for i in p['evidence_ids'] if i in hist]})
    rng.shuffle(items)
    packet_id=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
    out.write_text(json.dumps({'packet_id':packet_id,'items':items},indent=2,ensure_ascii=False),encoding='utf-8')
    (ROOT/'results/reply-review-key.json').write_text(json.dumps(key,indent=2),encoding='utf-8')
    print('Prepared 90 blinded replies: 30 calibration and 60 validation outputs; no human scores prefilled.')

if __name__=='__main__': main()
