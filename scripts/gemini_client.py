"""Google Gemini REST client with response caching, bounded retries and no key logging."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import threading
import urllib.error
import urllib.request


class Gemini:
    def __init__(self, model='gemini-3.8-flash', key_file=None, cache=None, min_interval=13, api_key=None,
                 request_timeout=90, max_attempts=6):
        if not re.fullmatch(r'gemini-[a-zA-Z0-9.\-]+',model): raise ValueError('Invalid model ID')
        self.model=model
        self.key=(api_key or '').strip() or (Path(key_file).read_text(encoding='utf-8').strip() if key_file else os.environ.get('GEMINI_API_KEY','').strip())
        self.cache=Path(cache) if cache else None
        self.min_interval=min_interval
        self.request_timeout=request_timeout
        self.max_attempts=max_attempts
        self.lock=threading.Lock()
        self.last_request=0

    def generate(self, instructions, data, schema):
        body={'systemInstruction':{'parts':[{'text':instructions}]},
              'contents':[{'role':'user','parts':[{'text':json.dumps(data,ensure_ascii=False)}]}],
              'generationConfig':{'maxOutputTokens':8192,'thinkingConfig':{'thinkingLevel':'low'},
                                  'responseMimeType':'application/json','responseJsonSchema':schema}}
        fingerprint=hashlib.sha256(json.dumps({'model':self.model,'body':body},sort_keys=True).encode()).hexdigest()
        cache_file=self.cache/(fingerprint+'.json') if self.cache else None
        if cache_file and cache_file.exists():
            record=json.loads(cache_file.read_text(encoding='utf-8'))
            return record['parsed'],dict(record['metadata'],cache_hit=True)
        if not self.key: raise RuntimeError('Set GEMINI_API_KEY locally or pass --key-file. Never commit keys.')
        url=f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
        request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','x-goog-api-key':self.key},method='POST')
        start=time.perf_counter()
        for attempt in range(self.max_attempts):
            with self.lock:
                delay=self.min_interval-(time.monotonic()-self.last_request)
                if delay>0: time.sleep(delay)
                self.last_request=time.monotonic()
            try:
                with urllib.request.urlopen(request,timeout=self.request_timeout) as response: raw=json.load(response)
                break
            except urllib.error.HTTPError as error:
                if error.code in (429,500,502,503,504) and attempt<self.max_attempts-1:
                    if error.code==429:
                        details=error.read().decode('utf-8','replace')
                        match=re.search(r'(?:retry in|retryDelay[^0-9]*)([0-9.]+)',details,re.I)
                        time.sleep((float(match.group(1)) if match else 15)+2)
                    else:
                        time.sleep(min(10*(attempt+1),55))
                    continue
                try:
                    info=json.loads(error.read()).get('error',{})
                    message=str(info.get('message','API request failed')).replace(self.key,'[redacted]')
                except Exception: message='API request failed'
                raise RuntimeError(f'Gemini HTTP {error.code}: {message[:400]}') from None
        candidates=raw.get('candidates',[])
        if not candidates: raise RuntimeError('Gemini returned no candidate (possibly safety-blocked).')
        candidate=candidates[0]
        if candidate.get('finishReason') not in ('STOP',None):
            raise RuntimeError('Gemini response incomplete: '+str(candidate.get('finishReason')))
        text=''.join(p.get('text','') for p in candidate.get('content',{}).get('parts',[]) if not p.get('thought'))
        parsed=json.loads(text)
        metadata={'model':self.model,'model_version':raw.get('modelVersion'),'request_sha256':fingerprint,
                  'usage':raw.get('usageMetadata',{}),'latency_ms':(time.perf_counter()-start)*1000,'cache_hit':False}
        if cache_file:
            cache_file.parent.mkdir(parents=True,exist_ok=True)
            cache_file.write_text(json.dumps({'parsed':parsed,'metadata':metadata},indent=2,ensure_ascii=False),encoding='utf-8')
        return parsed,metadata


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--key-file');parser.add_argument('--model',default='gemini-3.8-flash')
    args=parser.parse_args()
    try:
        answer,meta=Gemini(args.model,args.key_file).generate('Return the requested JSON.',{'request':'Set ok to true.'},{'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']})
        print(json.dumps({'connection':answer,'model':meta['model'],'model_version':meta['model_version']}))
    except Exception as error:
        print(str(error));raise SystemExit(1)
