"""Metrics keep routing-label disagreement separate from actual reply safety."""
from collections import Counter
import math
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support, cohen_kappa_score
from annotation_store import INTENTS


def wilson(success,total):
    if not total: return None
    z=1.96;p=success/total;den=1+z*z/total
    mid=(p+z*z/(2*total))/den
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [max(0,mid-half),min(1,mid+half)]


def evaluate(predictions,labels):
    truth=[labels[p['tweet_id']] for p in predictions]
    y=[t['intent'] for t in truth]; yp=[p['intent'] for p in predictions]
    auto=[i for i,p in enumerate(predictions) if p['route']=='auto_handle']
    need=[i for i,t in enumerate(truth) if t['route']=='escalate']
    caught=sum(predictions[i]['route']=='escalate' for i in need)
    disagreements=sum(truth[i]['route']=='escalate' for i in auto)
    precision,recall,f1,support=precision_recall_fscore_support(y,yp,labels=list(INTENTS),zero_division=0)
    return {'n':len(y),'intent_accuracy':accuracy_score(y,yp),'intent_macro_f1_all_8':f1_score(y,yp,labels=list(INTENTS),average='macro',zero_division=0),
            'intent_per_class':{k:dict(precision=float(precision[i]),recall=float(recall[i]),f1=float(f1[i]),support=int(support[i])) for i,k in enumerate(INTENTS)},
            'auto_count':len(auto),'auto_coverage':len(auto)/len(y) if y else None,
            'escalation_required_count':len(need),'escalation_recall':caught/len(need) if need else None,
            'auto_route_disagreements':disagreements,'auto_route_disagreement_rate':disagreements/len(auto) if auto else None,
            'auto_route_disagreement_wilson95':wilson(disagreements,len(auto)),
            'reply_kind_counts':dict(Counter(p.get('reply_kind','unknown') for p in predictions)),
            'reply_quality_measured':False}


def judge_agreement(human,judge):
    common=sorted(set(human)&set(judge))
    dimensions=('correctness','grounding','usefulness','routing_privacy')
    result={'n_paired':len(common),'dimensions':{}}
    for dimension in dimensions:
        pairs=[(human[i].get(dimension),judge[i].get(dimension)) for i in common]
        pairs=[p for p in pairs if p[0] in (0,1,2) and p[1] in (0,1,2)]
        if not pairs:
            result['dimensions'][dimension]={'n':0,'exact_agreement':None,'weighted_kappa':None};continue
        a,b=zip(*pairs)
        k=cohen_kappa_score(a,b,labels=[0,1,2],weights='linear') if len(pairs)>1 and len(set(a)|set(b))>1 else float('nan')
        result['dimensions'][dimension]={'n':len(pairs),'exact_agreement':sum(x==y for x,y in pairs)/len(pairs),'weighted_kappa':float(k) if math.isfinite(k) else None}
    binary=[i for i in common if isinstance(human[i].get('critical_failure'),bool) and isinstance(judge[i].get('critical_failure'),bool)]
    result['critical_failure_pairs']=len(binary)
    result['critical_failure_exact_agreement']=sum(human[i]['critical_failure']==judge[i]['critical_failure'] for i in binary)/len(binary) if binary else None
    result['judge_missed_human_critical_failures']=sum(human[i]['critical_failure'] and not judge[i]['critical_failure'] for i in binary)
    result['human_critical_failures']=sum(human[i]['critical_failure'] for i in binary)
    result['judge_critical_failure_recall']=((result['human_critical_failures']-result['judge_missed_human_critical_failures'])/result['human_critical_failures'] if result['human_critical_failures'] else None)
    return result
