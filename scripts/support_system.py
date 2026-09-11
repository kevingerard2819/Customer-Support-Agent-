"""Reproducible offline baselines and guarded retrieval comparator.

Only the caller-provided development labels enter fit(). No test labels are read here.
"""
from collections import Counter
import html
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from annotation_store import INTENTS

CONFIG = {'version':'offline-v1', 'tfidf_ngrams':[1,2], 'classifier_C':1.0,
          'retrieval_k':3, 'simple_min_similarity':0.25,
          'guarded_min_similarity':0.30, 'random_state':42}


def clean(text):
    text=html.unescape(text)
    text=re.sub(r'https?://\S+|@[\w_]+',' ',text)
    return re.sub(r'\s+',' ',text).strip()


def input_text(example):
    # Same past-only context is available to every nontrivial system.
    context=' '.join(c['text'] for c in example.get('context',[])[-4:])
    return clean(context+' '+example['message']+' '+example['message'])


def privacy_redact(text):
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[email redacted]', text)
    text=re.sub(r'\b(?:\d[ -]?){9,16}\b','[number redacted]',text)
    return re.sub(r'@[\w_]+','[user]',text)


class Systems:
    def __init__(self, development, labels, history):
        if any(e['split']!='dev' for e in development):
            raise ValueError('Training may only use development examples')
        self.history=history
        y=[labels[e['tweet_id']]['intent'] for e in development]
        self.majority=Counter(y).most_common(1)[0][0]
        self.training_counts=dict(Counter(y))
        self.vector=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,max_features=15000)
        x=self.vector.fit_transform([input_text(e) for e in development])
        self.clf=LogisticRegression(C=CONFIG['classifier_C'],class_weight='balanced',max_iter=1000,random_state=42).fit(x,y)
        self.retriever=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,max_features=50000)
        self.history_matrix=self.retriever.fit_transform([clean(h['customer_message']) for h in history])

    def retrieve(self, example):
        q=self.retriever.transform([input_text(example)])
        similarities=(self.history_matrix@q.T).toarray().ravel()
        indexes=np.argsort(-similarities,kind='stable')[:CONFIG['retrieval_k']]
        return [dict(self.history[int(i)],similarity=float(similarities[i])) for i in indexes if similarities[i]>0]

    def classify(self, example):
        p=self.clf.predict_proba(self.vector.transform([input_text(example)]))[0]
        index=int(np.argmax(p))
        return str(self.clf.classes_[index]),float(p[index])

    def predict(self, example, system):
        if system=='trivial':
            return dict(intent=self.majority,route='escalate',reason='Always-human baseline.',
                        draft='Thanks for reaching out. This needs a human support review.',evidence_ids=[],reply_kind='handoff',confidence=None)
        intent,confidence=self.classify(example)
        evidence=self.retrieve(example)
        score=evidence[0]['similarity'] if evidence else 0
        if system=='simple':
            route='auto_handle' if score>=CONFIG['simple_min_similarity'] and intent not in ('billing_subscription','account_access_security','other_unclear') else 'escalate'
            draft=privacy_redact(clean(evidence[0]['historical_reply'])) if evidence else 'Please describe the issue so support can help.'
            return dict(intent=intent,route=route,reason=f'Nearest-reply baseline: similarity {score:.3f}; predicted intent {intent}.',draft=draft,
                        evidence_ids=[evidence[0]['support_tweet_id']] if evidence else [],reply_kind='historical_reply',confidence=confidence)
        if system!='guarded_retrieval': raise ValueError(system)
        return guarded_reply(example,intent,confidence,evidence)


def risk_reason(example,intent):
    text=clean(example['message']).lower()
    if re.search(r'kill myself|suicid|hurt myself|end my life',text): return 'Sensitive distress requires human review.'
    if re.search(r'hack|stolen|unauthori[sz]ed|__email__|password|charged|refund|charge me|double|charged twice',text):
        return 'Account, payment or security information requires human verification.'
    if intent in ('billing_subscription','account_access_security'): return 'Account or subscription issue requires a human.'
    if any(example.get('context_status',{}).values()): return 'Earlier context is incomplete or inconsistent.'
    if intent=='other_unclear': return 'Intent or scope is unclear.'
    if re.search(r'already|still|again|tried|no it doesn|not fix|for months',text): return 'Prior attempts or an unresolved follow-up require human review.'
    if re.search(r'\b(bump|any update|update on this)\b',text): return 'Follow-up needs human review of the unresolved issue.'
    # Conservative heuristic only; not a validated language detector.
    if text and sum(ord(c)>127 for c in text)/len(text)>.25: return 'Language support is uncertain.'
    return None


def guarded_reply(example,intent,confidence,evidence):
    reason=risk_reason(example,intent)
    draft='A human support specialist needs to review this. Please use a private support channel for any account details; do not post passwords or payment information here.'
    result=dict(intent=intent,route='escalate',reason=reason or 'Insufficient evidence for an automatic reply.',draft=draft,evidence_ids=[],reply_kind='handoff',confidence=confidence)
    if reason:
        if 'distress' in reason:
            result['draft']="I'm sorry you're going through this. Your safety matters, and this needs a person's attention. If you may act on thoughts of harming yourself, contact local emergency help or someone you trust now."
        return result
    if not evidence or evidence[0]['similarity']<CONFIG['guarded_min_similarity']: return result
    for e in evidence:
        history=clean(e['historical_reply']).lower()
        if intent=='social_acknowledgement' and re.search(r'welcome|no worries|happy to help|glad',history):
            result.update(route='auto_handle',reason='Low-risk acknowledgement supported by a historical example.',draft="You're welcome. Let us know if you need anything else.",evidence_ids=[e['support_tweet_id']],reply_kind='acknowledgement')
            return result
        if intent=='playback_app' and re.search(r'device|operating system|app version|spotify version',history):
            result.update(route='auto_handle',reason='Historical replies support asking for non-sensitive troubleshooting details.',draft='What device, operating system and Spotify app version are you using, and what happens when the issue occurs?',evidence_ids=[e['support_tweet_id']],reply_kind='clarification')
            return result
        if intent=='feedback_feature_request' and re.search(r'feedback|idea|suggestion',history):
            result.update(route='auto_handle',reason='Acknowledges feedback without claiming an internal action or future release.',draft='Thanks for sharing this suggestion. What would you like that feature to let you do?',evidence_ids=[e['support_tweet_id']],reply_kind='clarification')
            return result
    return result
