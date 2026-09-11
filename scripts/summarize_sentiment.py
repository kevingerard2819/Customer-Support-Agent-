"""Describe deterministic sentiment signals on the frozen 200-example packet."""
from collections import Counter,defaultdict
import json
from pathlib import Path

from sentiment import analyze_sentiment


def main():
    root=Path(__file__).resolve().parents[1]
    packet=json.loads((root/'annotations/batch-200.json').read_text(encoding='utf-8'))
    labels=json.loads((root/'annotations/golden-completed.json').read_text(encoding='utf-8'))['labels']
    split_counts=defaultdict(Counter);intent_counts=defaultdict(Counter);examples=[]
    for item in packet['examples']:
        signal=analyze_sentiment(item['message']);split_counts[item['split']][signal['label']]+=1
        intent_counts[labels[item['tweet_id']]['intent']][signal['label']]+=1
        examples.append({'tweet_id':item['tweet_id'],'split':item['split'],'sentiment':signal})
    report={
        'method':'Deterministic lexicon/phrase/emoji heuristic v1; used for tone, not reported as a validated classifier.',
        'by_split':{k:dict(v) for k,v in split_counts.items()},
        'by_human_intent':{k:dict(v) for k,v in intent_counts.items()},
        'examples':examples,
    }
    out=root/'results/sentiment-profile.json';out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'by_split':report['by_split']},indent=2))


if __name__=='__main__':main()
