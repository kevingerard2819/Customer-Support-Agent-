"""One-command offline comparison, cached predictions, report and blinded rating packet."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import time
from annotation_store import INTENTS
from support_system import Systems,CONFIG
from metrics import evaluate


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();root=args.repo
    out=args.output or root/'results/offline-v1'
    if (out/'manifest.json').exists():
        raise SystemExit('This run already exists. Use --output with a new directory; existing results are immutable.')
    packet=json.loads((root/'annotations/batch-200.json').read_text(encoding='utf-8'))
    gold=json.loads((root/'annotations/golden-completed.json').read_text(encoding='utf-8'))
    if gold['packet_id']!=packet['packet_id']: raise ValueError('Mismatched labels')
    examples=packet['examples']; labels=gold['labels']
    if any(labels.get(e['tweet_id'],{}).get('intent') not in INTENTS or labels.get(e['tweet_id'],{}).get('route') not in ('escalate','auto_handle') for e in examples):
        raise ValueError('Missing or invalid human labels')
    dev=[e for e in examples if e['split']=='dev']
    history=json.loads((root/'data/retrieval/history.json').read_text(encoding='utf-8'))
    started=time.perf_counter()
    system=Systems(dev,{e['tweet_id']:labels[e['tweet_id']] for e in dev},history)
    systems=('trivial','simple','guarded_retrieval')
    config_hash=hashlib.sha256(json.dumps(CONFIG,sort_keys=True).encode()).hexdigest()
    # Freeze implementation/config before evaluating test targets.
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'packet_id':packet['packet_id'],
              'config':CONFIG,'config_sha256':config_hash,'labels_sha256':sha(root/'annotations/golden-completed.json'),
              'source_sha256':{p.name:sha(p) for p in [root/'scripts/support_system.py',root/'scripts/metrics.py',Path(__file__)]},
              'training_ids':[e['tweet_id'] for e in dev],'training_class_counts':system.training_counts,
              'unseen_training_intents':[i for i in INTENTS if i not in system.training_counts],
              'hyperparameter_selection':'Fixed settings chosen before test scores; no held-out tuning.',
              'dependencies':{p:importlib.metadata.version(p) for p in ('scikit-learn','numpy','scipy')},
              'llm_status':'Not run: provider/key not configured. Guarded retrieval is a template comparator, not an LLM.',
              'human_judge_agreement_status':'Not measured; requires independently entered reply ratings and LLM judge scores.'}
    write(out/'manifest.json',manifest)
    predictions=[]
    for name in systems:
        for e in examples:
            tick=time.perf_counter()
            prediction=system.predict(e,name)
            prediction.update(tweet_id=e['tweet_id'],system=name,split=e['split'],latency_ms=(time.perf_counter()-tick)*1000)
            predictions.append(prediction)
    write(out/'predictions.json',predictions)
    results={name:{split:evaluate([p for p in predictions if p['system']==name and p['split']==split],labels)
                   for split in ('dev','test_representative','test_challenge')} for name in systems}
    write(out/'metrics.json',results)
    # Save development-only label consistency observations separately, never change labels.
    audit=[{'tweet_id':e['tweet_id'],'issue':'Routing reason conflicts with selected route','label':labels[e['tweet_id']]}
           for e in dev if (labels[e['tweet_id']].get('reason','').startswith(('safe_','supported_')) and labels[e['tweet_id']]['route']=='escalate')
           or (labels[e['tweet_id']].get('reason') in ('account_action','security_privacy','sensitive_safety') and labels[e['tweet_id']]['route']=='auto_handle')]
    write(out/'development-label-audit.json',audit)
    # Blind rating packet: 10 dev calibration + 20 test validation inputs, every system paired on each.
    rng=random.Random(778)
    rating_examples=rng.sample(dev,10)+rng.sample([e for e in examples if e['split']=='test_representative'],20)
    ratings=[];key={}
    pred_index={(p['system'],p['tweet_id']):p for p in predictions}
    hist_index={h['support_tweet_id']:h for h in history}
    for e in rating_examples:
        for name in systems:
            p=pred_index[name,e['tweet_id']]
            rid=hashlib.sha256((name+e['tweet_id']+'rating-v1').encode()).hexdigest()[:12]
            key[rid]={'system':name,'tweet_id':e['tweet_id'],'partition':'calibration' if e['split']=='dev' else 'validation'}
            ratings.append({'rating_id':rid,'message':e['message'],'context':e['context'],'draft':p['draft'],'route':p['route'],
                            'evidence':[hist_index[i] for i in p['evidence_ids'] if i in hist_index]})
    rng.shuffle(ratings)
    write(out/'reply-rating-packet.json',{'status':'unrated','items':ratings})
    write(out/'reply-rating-key.json',key)
    # Automated errors are candidates for inspection, not hand-validated root causes.
    error_rows=[dict(p,human_intent=labels[p['tweet_id']]['intent'],human_route=labels[p['tweet_id']]['route'])
                for p in predictions if p['split']!='dev' and (p['intent']!=labels[p['tweet_id']]['intent'] or p['route']!=labels[p['tweet_id']]['route'])]
    write(out/'errors-for-review.json',error_rows)
    lines=['# Offline evaluation results','','These are measured intent/routing results against the original human labels. Reply safety and quality are not yet measured. The LLM agent and LLM judge have not run.','',
           '| System | Test subset | n | Intent macro-F1 (8 classes) | Auto coverage | Escalation recall | Auto-route disagreements |',
           '|---|---|---:|---:|---:|---:|---:|']
    for name in systems:
        for split in ('test_representative','test_challenge'):
            m=results[name][split];recall='n/a' if m['escalation_recall'] is None else f"{m['escalation_recall']:.1%}"
            lines.append(f"| {name} | {split} | {m['n']} | {m['intent_macro_f1_all_8']:.3f} | {m['auto_coverage']:.1%} | {recall} | {m['auto_route_disagreements']}/{m['auto_count']} |")
    lines += ['', '## What is misleading about these numbers?', '',
              '- Auto-route disagreement measures disagreement with a human routing label, not whether a reply is actually safe or correct.',
              '- Always escalating achieves perfect escalation recall with zero automation. A missing rate with no automatic replies is not zero risk.',
              '- The guarded comparator uses templates; its auto replies are acknowledgements or clarifications, not demonstrated issue resolutions.',
              '- Macro-F1 averages all eight predefined intents, including classes absent from development training. See the manifest for training support.',
              '- Original labels are preserved despite development-set taxonomy/reason inconsistencies; they have not had independent second-human adjudication.',
              '- The representative set excludes duplicate/overlapping and multi-brand conversations. The challenge set is deliberately enriched and is reported separately.',
              '- Historical responses and UI/policy claims may be stale; public DM redirects do not expose the actual resolution.',
              '- Test results must not drive subsequent tuning. Freeze any later version before evaluation, and disclose repeated test exposure.',
              '', '## Remaining evidence', '', 'Live LLM predictions, independent human reply ratings, judge agreement, and a manually inspected five-mode failure analysis are pending. Do not submit this as a finished assignment.',
              '',f'Runtime for this run: {time.perf_counter()-started:.2f} seconds.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'seconds':round(time.perf_counter()-started,2),'prediction_count':len(predictions),'rating_items':len(ratings),'training_counts':system.training_counts,'test_metrics':{n:results[n]['test_representative'] for n in systems}},indent=2))


if __name__=='__main__': main()
