"""Recover a checked partial run using smaller batches; preserves all accepted outputs."""
import argparse
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
from gemini_client import Gemini
from run_gemini import INSTRUCTIONS,SCHEMA,gate,save
from support_system import Systems,privacy_redact
from metrics import evaluate

def main():
    p=argparse.ArgumentParser();p.add_argument('--key-file');p.add_argument('--model',default='gemini-3.5-flash');args=p.parse_args()
    root=Path(__file__).resolve().parents[1];partial=root/'results/gemini-3.5-v1';out=root/'results/gemini-3.5-final-v1'
    packet=json.loads((root/'annotations/batch-200.json').read_text(encoding='utf-8'));gold=json.loads((root/'annotations/golden-completed.json').read_text(encoding='utf-8'))
    accepted=json.loads((partial/'predictions.json').read_text(encoding='utf-8'))
    if len(accepted)!=120 or len({x['tweet_id'] for x in accepted})!=120:raise ValueError('Expected checked 120-record partial run')
    history=json.loads((root/'data/retrieval/history.json').read_text(encoding='utf-8'));dev=[e for e in packet['examples'] if e['split']=='dev']
    helpers=Systems(dev,{e['tweet_id']:gold['labels'][e['tweet_id']] for e in dev},history)
    instructions=INSTRUCTIONS+'\nGUIDE:\n'+(root/'docs/annotation-guide.md').read_text(encoding='utf-8')+'\nProcess each item independently. Use only that item\'s context and records. Return exactly one result per supplied tweet_id.'
    item_schema=dict(SCHEMA,properties=dict(SCHEMA['properties'],tweet_id={'type':'string'}),required=SCHEMA['required']+['tweet_id'])
    schema={'type':'object','properties':{'results':{'type':'array','minItems':10,'maxItems':10,'items':item_schema}},'required':['results']}
    manifest={'model':args.model,'packet_id':packet['packet_id'],'accepted_partial_count':120,'recovery_batch_size':10,
              'partial_manifest_sha256':hashlib.sha256((partial/'manifest.json').read_bytes()).hexdigest(),
              'prompt_sha256':hashlib.sha256(instructions.encode()).hexdigest(),'created_at':datetime.now(timezone.utc).isoformat(),
              'note':'Preserved 120 accepted v1 outputs. The next 20-item response failed exact ID validation and was not accepted. Remaining 80 recovered in exact 10-item batches.'}
    if (out/'manifest.json').exists():
        old=json.loads((out/'manifest.json').read_text());
        for key in ('model','packet_id','partial_manifest_sha256','prompt_sha256'):
            if old[key]!=manifest[key]:raise ValueError('Recovery run changed')
    else:save(out/'manifest.json',manifest)
    predictions=list(accepted);done={x['tweet_id'] for x in predictions};remaining=[e for e in packet['examples'] if e['tweet_id'] not in done]
    client=Gemini(args.model,args.key_file,out/'cache')
    for start in range(0,len(remaining),10):
        examples=remaining[start:start+10];evidence={e['tweet_id']:helpers.retrieve(e) for e in examples}
        items=[{'tweet_id':e['tweet_id'],'message':privacy_redact(e['message']),'context':[dict(c,text=privacy_redact(c['text'])) for c in e['context'][-4:]],
                'context_status':e['context_status'],'historical_records':[dict(h,customer_message=privacy_redact(h['customer_message']),historical_reply=privacy_redact(h['historical_reply'])) for h in evidence[e['tweet_id']]]} for e in examples]
        raw,metadata=client.generate(instructions,{'items':items},schema);responses=raw['results']
        if len(responses)!=10 or {r.get('tweet_id') for r in responses}!={e['tweet_id'] for e in examples}:raise ValueError('Recovery batch failed exact ID check')
        by_id={r['tweet_id']:r for r in responses}
        for e in examples:
            original=by_id[e['tweet_id']];prediction=gate(original,e,evidence[e['tweet_id']])
            prediction.update(tweet_id=e['tweet_id'],split=e['split'],system='gemini',raw_prediction=original,api_error=None,api_metadata=metadata,latency_ms=metadata['latency_ms']/10)
            predictions.append(prediction);save(out/'individual'/f"{e['tweet_id']}.json",prediction)
        order={e['tweet_id']:i for i,e in enumerate(packet['examples'])};predictions.sort(key=lambda x:order[x['tweet_id']]);save(out/'predictions.json',predictions)
        print(f'Gemini accepted: {len(predictions)}/200',flush=True)
    if len(predictions)!=200 or len({x['tweet_id'] for x in predictions})!=200:raise ValueError('Final Gemini output incomplete')
    save(out/'metrics.json',{split:evaluate([r for r in predictions if r['split']==split],gold['labels']) for split in ('dev','test_representative','test_challenge')})
    save(out/'run-status.json',{'completed':200,'validated_unique_ids':200,'error':None})
    print('Recovered Gemini run complete.')

if __name__=='__main__':main()
