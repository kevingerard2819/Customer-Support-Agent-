"""Rate-limited, cached batches of eight independent support examples."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from gemini_client import Gemini
from run_gemini import INSTRUCTIONS, SCHEMA, gate, save
from support_system import Systems,privacy_redact
from metrics import evaluate

def main():
    p=argparse.ArgumentParser();p.add_argument('--key-file');p.add_argument('--model',default='gemini-3.7-flash');p.add_argument('--batch-size',type=int,default=20);p.add_argument('--output',type=Path)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];out=args.output or root/'results/gemini-3.7-v1'
    if not 1 <= args.batch_size <= 20: raise ValueError('Batch size must be 1-20')
    packet=json.loads((root/'annotations/batch-200.json').read_text(encoding='utf-8'))
    gold=json.loads((root/'annotations/golden-completed.json').read_text(encoding='utf-8'))
    assert packet['packet_id']==gold['packet_id']
    history=json.loads((root/'data/retrieval/history.json').read_text(encoding='utf-8'))
    dev=[e for e in packet['examples'] if e['split']=='dev']
    helpers=Systems(dev,{e['tweet_id']:gold['labels'][e['tweet_id']] for e in dev},history)
    instructions=INSTRUCTIONS+'\nGUIDE:\n'+(root/'docs/annotation-guide.md').read_text(encoding='utf-8')+'\nProcess each item independently. Use only that item\'s context and records; never use another item as evidence. Return exactly one result per supplied tweet_id.'
    item_schema=dict(SCHEMA,properties=dict(SCHEMA['properties'],tweet_id={'type':'string'}),required=SCHEMA['required']+['tweet_id'])
    schema={'type':'object','properties':{'results':{'type':'array','items':item_schema}},'required':['results']}
    signature=hashlib.sha256((instructions+json.dumps(schema,sort_keys=True)+Path(__file__).read_text()).encode()).hexdigest()
    manifest={'model':args.model,'signature':signature,'packet_id':packet['packet_id'],'batch_size':args.batch_size,
              'note':'Twenty independent items per request to reduce API calls. Earlier Gemini 3.8 runs stopped on quota/high-demand errors; no tuning on their test outputs. Original human labels unchanged.',
              'created_at':datetime.now(timezone.utc).isoformat()}
    if (out/'manifest.json').exists():
        previous=json.loads((out/'manifest.json').read_text())
        if previous['signature']!=signature or previous['model']!=args.model: raise ValueError('Frozen run changed')
    else: save(out/'manifest.json',manifest)
    save(out/'prompt.json',{'instructions':instructions,'schema':schema})
    client=Gemini(args.model,args.key_file,out/'cache')
    all_predictions=[]
    for start in range(0,len(packet['examples']),args.batch_size):
        examples=packet['examples'][start:start+args.batch_size]
        evidence={e['tweet_id']:helpers.retrieve(e) for e in examples}
        items=[{'tweet_id':e['tweet_id'],'message':privacy_redact(e['message']),
                'context':[dict(c,text=privacy_redact(c['text'])) for c in e['context'][-4:]],'context_status':e['context_status'],
                'historical_records':[dict(h,customer_message=privacy_redact(h['customer_message']),historical_reply=privacy_redact(h['historical_reply'])) for h in evidence[e['tweet_id']]]} for e in examples]
        try:
            raw,metadata=client.generate(instructions,{'items':items},schema)
            responses=raw['results']
            if len(responses)!=len(examples) or {r['tweet_id'] for r in responses}!={e['tweet_id'] for e in examples}: raise ValueError('Batch IDs incomplete or duplicated')
            by_id={r['tweet_id']:r for r in responses}
            for e in examples:
                original=by_id[e['tweet_id']]
                prediction=gate(original,e,evidence[e['tweet_id']])
                prediction.update(tweet_id=e['tweet_id'],split=e['split'],system='gemini',raw_prediction=original,
                                  api_error=None,api_metadata=metadata,latency_ms=metadata['latency_ms']/len(examples))
                all_predictions.append(prediction)
                save(out/'individual'/f"{e['tweet_id']}.json",prediction)
        except Exception as error:
            save(out/'run-status.json',{'completed':len(all_predictions),'total':200,'error':str(error),'resume':'Run the same command; successful request batches are cached.'})
            raise
        save(out/'predictions.json',all_predictions)
        save(out/'run-status.json',{'completed':len(all_predictions),'total':200,'error':None})
        print(f'Gemini: {len(all_predictions)}/200 saved',flush=True)
    save(out/'metrics.json',{split:evaluate([r for r in all_predictions if r['split']==split],gold['labels']) for split in ('dev','test_representative','test_challenge')})
    print('Gemini run complete.',flush=True)

if __name__=='__main__': main()
