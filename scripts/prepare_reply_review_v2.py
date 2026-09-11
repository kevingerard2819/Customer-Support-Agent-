"""Create a tone-normalized v2 review packet while preserving the frozen v1 review."""
import hashlib
import json
from pathlib import Path
import re

from run_gemini import STYLE_VERSION, gate, handoff_draft, polish_draft
from support_system import risk_reason


ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def main():
    output=ROOT/'annotations/reply-review-packet-v2.json'
    if output.exists():raise SystemExit('v2 packet already exists; refusing to invalidate ratings.')
    old_packet=read(ROOT/'annotations/reply-review-packet.json')
    old_key=read(ROOT/'results/reply-review-key.json')
    examples={e['tweet_id']:e for e in read(ROOT/'annotations/batch-200.json')['examples']}
    predictions=read(ROOT/'results/offline-v1/predictions.json')+read(ROOT/'results/gemini-3.5-final-v1/predictions.json')
    prediction_index={(p['system'],p['tweet_id']):p for p in predictions}
    items=[];key={};changes=[]
    for old_item in old_packet['items']:
        identity=old_key[old_item['rating_id']];system=identity['system'];tweet_id=identity['tweet_id']
        prediction=prediction_index[(system,tweet_id)]
        item=dict(old_item);draft,adjustments=polish_draft(item['draft'])
        if system=='gemini':
            # Reapply the current gate to the frozen raw output. This changes
            # tone and can conservatively change a route, but makes no API call.
            revised=gate(dict(prediction['raw_prediction']),examples[tweet_id],old_item['evidence'])
            draft=revised['draft'];item['route']=revised['route']
            allowed=set(revised['evidence_ids']);item['evidence']=[e for e in old_item['evidence'] if e['support_tweet_id'] in allowed]
            adjustments.extend(revised['style_adjustments'])
            if revised['output_check_violations']:adjustments.append('v2 safety gate')
        elif system=='trivial' and item['route']=='escalate':
            reason=risk_reason(examples[tweet_id],None) or prediction.get('reason','')
            draft=handoff_draft(examples[tweet_id],None,reason)
            adjustments.append('generic baseline handoff')
        new_id=hashlib.sha256((old_item['rating_id']+STYLE_VERSION).encode()).hexdigest()[:12]
        item.update(rating_id=new_id,draft=draft)
        key[new_id]=dict(identity,source_rating_id=old_item['rating_id'],style_version=STYLE_VERSION)
        items.append(item)
        if draft!=old_item['draft']:changes.append({'rating_id':new_id,'system':system,'tweet_id':tweet_id,'adjustments':adjustments})
    packet_id=hashlib.sha256(json.dumps(items,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    write(output,{'packet_id':packet_id,'version':'reply-review-v2','style_version':STYLE_VERSION,'items':items})
    write(ROOT/'results/reply-review-key-v2.json',key)
    write(ROOT/'results/reply-review-v2-manifest.json',{
        'packet_id':packet_id,'source_packet_id':old_packet['packet_id'],'style_version':STYLE_VERSION,
        'item_count':len(items),'changed_draft_count':len(changes),'changes':changes,
        'note':'The frozen v1 packet and human ratings remain unchanged. Tone normalization is applied without LLM calls.'
    })
    print(json.dumps({'packet':str(output),'items':len(items),'changed_drafts':len(changes)},indent=2))


if __name__=='__main__':main()
