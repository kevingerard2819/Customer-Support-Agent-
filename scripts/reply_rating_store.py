"""Atomic storage for independent human reply-quality ratings."""
from pathlib import Path
import json
from datetime import datetime,timezone
from annotation_store import atomic_json

DIMS=('correctness','grounding','usefulness','routing_privacy')

class RatingStore:
    def __init__(self,packet_path,progress_path):
        self.packet=json.loads(Path(packet_path).read_text(encoding='utf-8'))
        self.items={x['rating_id']:x for x in self.packet['items']}
        if len(self.items)!=len(self.packet['items']): raise ValueError('Duplicate rating IDs')
        self.path=Path(progress_path)
        if self.path.exists():
            self.data=json.loads(self.path.read_text(encoding='utf-8'));self.validate(self.data)
        else:
            self.data={'packet_id':self.packet['packet_id'],'rubric_version':'v1','source':'human_entries_in_local_reply_tool','ratings':{}}

    def validate(self,data):
        if data.get('packet_id')!=self.packet['packet_id']: raise ValueError('Ratings belong to another packet')
        ratings=data.get('ratings')
        if not isinstance(ratings,dict) or not set(ratings)<=set(self.items): raise ValueError('Unknown rating IDs')
        for value in ratings.values():
            if any(value.get(k) not in ('',0,1,2) for k in DIMS): raise ValueError('Scores must be blank or 0-2')
            if value.get('critical_failure') not in ('',True,False): raise ValueError('Critical failure must be blank, yes or no')
            if not isinstance(value.get('notes',''),str): raise ValueError('Notes must be text')

    def update(self,rating_id,**fields):
        if rating_id not in self.items: raise ValueError('Unknown rating ID')
        candidate=json.loads(json.dumps(self.data))
        value=dict(candidate['ratings'].get(rating_id,{}));value.update(fields)
        value['updated_at']=datetime.now(timezone.utc).isoformat();candidate['ratings'][rating_id]=value
        self.validate(candidate);atomic_json(self.path,candidate);self.data=candidate

    def complete(self):
        return sum(all(v.get(k) in (0,1,2) for k in DIMS) and isinstance(v.get('critical_failure'),bool) for v in self.data['ratings'].values())

