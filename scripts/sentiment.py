"""Small, transparent sentiment/tone heuristic for noisy support tweets.

This is a response-style signal, not a validated sentiment classifier. Explicit
distress is kept separate because it affects safety routing.
"""
import html
import re


POSITIVE=(
    'thank you','thanks','love','awesome','amazing','great','excellent','happy',
    'helpful','perfect','fixed','works now','appreciate','nice','glad','wonderful',
    'got access','have access','finally have access',
)
NEGATIVE=(
    'hate','awful','terrible','horrible','frustrating','frustrated','disappointed',
    'angry','annoyed','broken','not working','does not work',"doesn't work",'cannot',
    "can't","won't",'error','problem','issue','charged twice','charged three times',
    'double charged','absurd','useless','sucks','worst','ridiculous','fed up',
)
DISTRESS_RE=re.compile(r'\b(?:kill myself|suicid(?:e|al)?|hurt myself|end my life|self[- ]harm)\b',re.I)
POSITIVE_EMOJI=('😊','😁','😍','❤️','❤','👍','🎉')
NEGATIVE_EMOJI=('😡','😠','😭','😢','💔','🤬','😞')


def _hits(text,terms):
    return [term for term in terms if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text)]


def analyze_sentiment(text):
    normalized=html.unescape(text).casefold()
    if DISTRESS_RE.search(normalized):
        return {'label':'distressed','score':-1.0,'intensity':'high','positive_hits':0,'negative_hits':1}
    positive=len(_hits(normalized,POSITIVE))+sum(normalized.count(x) for x in POSITIVE_EMOJI)
    negative=len(_hits(normalized,NEGATIVE))+sum(normalized.count(x) for x in NEGATIVE_EMOJI)
    if positive and negative:label='mixed'
    elif positive:label='positive'
    elif negative:label='negative'
    else:label='neutral'
    score=(positive-negative)/max(1,positive+negative)
    emphatic='!!!' in text or bool(re.search(r'\b[A-Z]{5,}\b',text))
    intensity='high' if emphatic or abs(score)>=1 and positive+negative>=2 else ('medium' if positive+negative else 'low')
    return {'label':label,'score':round(score,3),'intensity':intensity,'positive_hits':positive,'negative_hits':negative}


def tone_guidance(signal):
    label=signal['label']
    if label=='distressed':return 'Use calm, direct, safety-first language. Do not use cheerfulness or emojis.'
    if label=='negative':return 'Acknowledge the frustration once, then give a clear next step. Do not sound defensive.'
    if label=='mixed':return 'Acknowledge both the appreciation and the unresolved problem without overdoing empathy.'
    if label=='positive':return 'Respond warmly and briefly; do not turn a simple acknowledgement into a support script.'
    return 'Use a concise, neutral and helpful tone.'
