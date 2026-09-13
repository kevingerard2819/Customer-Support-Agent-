"""Google Gemini REST client with response caching, bounded retries, auto-model fallback and no key logging."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import threading
import urllib.error
import urllib.request


DEFAULT_FALLBACK_CHAIN = [
    'gemini-3.8-flash',
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.5-flash',
    'gemini-2.5-flash',
    'gemini-1.5-flash',
]


def resolve_model_chain(model_spec):
    """Normalize model string or list into an ordered fallback list."""
    if not model_spec or str(model_spec).strip().lower() in ('auto', 'default'):
        return list(DEFAULT_FALLBACK_CHAIN)
    if isinstance(model_spec, (list, tuple)):
        models = [str(m).strip() for m in model_spec if m and str(m).strip()]
    elif isinstance(model_spec, str):
        if ',' in model_spec:
            models = [m.strip() for m in model_spec.split(',') if m.strip()]
        else:
            models = [model_spec.strip()]
    else:
        models = list(DEFAULT_FALLBACK_CHAIN)

    validated = []
    for m in models:
        if not re.fullmatch(r'gemini-[a-zA-Z0-9.\-]+', m):
            raise ValueError(f'Invalid model ID: {m}')
        if m not in validated:
            validated.append(m)

    # Append standard fallbacks after the preferred models if not already included
    for default_m in DEFAULT_FALLBACK_CHAIN:
        if default_m not in validated:
            validated.append(default_m)
    return validated


class Gemini:
    def __init__(self, model='auto', key_file=None, cache=None, min_interval=13, api_key=None,
                 request_timeout=60, max_attempts=3, auto_fallback=True):
        self.models = resolve_model_chain(model) if auto_fallback else ([model] if isinstance(model, str) else list(model))
        self.model = self.models[0]
        self.auto_fallback = auto_fallback
        self.key = (api_key or '').strip() or (Path(key_file).read_text(encoding='utf-8').strip() if key_file else os.environ.get('GEMINI_API_KEY','').strip())
        self.cache = Path(cache) if cache else None
        self.min_interval = min_interval
        self.request_timeout = request_timeout
        self.max_attempts = max_attempts
        self.lock = threading.Lock()
        self.last_request = 0

    def _call_model(self, model_name, instructions, data, schema):
        body = {
            'systemInstruction': {'parts': [{'text': instructions}]},
            'contents': [{'role': 'user', 'parts': [{'text': json.dumps(data, ensure_ascii=False)}]}],
            'generationConfig': {
                'maxOutputTokens': 8192,
                'thinkingConfig': {'thinkingLevel': 'low'},
                'responseMimeType': 'application/json',
                'responseJsonSchema': schema
            }
        }
        fingerprint = hashlib.sha256(json.dumps({'model': model_name, 'body': body}, sort_keys=True).encode()).hexdigest()
        cache_file = self.cache / (fingerprint + '.json') if self.cache else None
        if cache_file and cache_file.exists():
            record = json.loads(cache_file.read_text(encoding='utf-8'))
            return record['parsed'], dict(record['metadata'], cache_hit=True, attempted_model=model_name)

        if not self.key:
            raise RuntimeError('Set GEMINI_API_KEY locally or pass --key-file. Never commit keys.')

        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent'
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'x-goog-api-key': self.key},
            method='POST'
        )
        start = time.perf_counter()
        raw = None
        for attempt in range(self.max_attempts):
            with self.lock:
                delay = self.min_interval - (time.monotonic() - self.last_request)
                if delay > 0:
                    time.sleep(delay)
                self.last_request = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                    raw = json.load(response)
                break
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise RuntimeError(f"Gemini model '{model_name}' not available (HTTP 404)") from None
                if error.code in (429, 500, 502, 503, 504) and attempt < self.max_attempts - 1:
                    if error.code == 429:
                        details = error.read().decode('utf-8', 'replace')
                        match = re.search(r'(?:retry in|retryDelay[^0-9]*)([0-9.]+)', details, re.I)
                        time.sleep((float(match.group(1)) if match else 10) + 1)
                    else:
                        time.sleep(min(5 * (attempt + 1), 30))
                    continue
                try:
                    info = json.loads(error.read()).get('error', {})
                    message = str(info.get('message', 'API request failed')).replace(self.key, '[redacted]')
                except Exception:
                    message = 'API request failed'
                raise RuntimeError(f"Gemini HTTP {error.code} on '{model_name}': {message[:400]}") from None
            except urllib.error.URLError as error:
                if attempt < self.max_attempts - 1:
                    time.sleep(min(3 * (attempt + 1), 15))
                    continue
                raise RuntimeError(f"Connection error on '{model_name}': {str(error)}") from None

        if raw is None:
            raise RuntimeError(f"No response received from model '{model_name}'")

        candidates = raw.get('candidates', [])
        if not candidates:
            raise RuntimeError(f"Gemini ({model_name}) returned no candidate (possibly safety-blocked).")
        candidate = candidates[0]
        if candidate.get('finishReason') not in ('STOP', None):
            raise RuntimeError(f"Gemini ({model_name}) response incomplete: " + str(candidate.get('finishReason')))
        text = ''.join(p.get('text', '') for p in candidate.get('content', {}).get('parts', []) if not p.get('thought'))
        parsed = json.loads(text)
        metadata = {
            'model': model_name,
            'model_version': raw.get('modelVersion') or model_name,
            'request_sha256': fingerprint,
            'usage': raw.get('usageMetadata', {}),
            'latency_ms': (time.perf_counter() - start) * 1000,
            'cache_hit': False
        }
        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({'parsed': parsed, 'metadata': metadata}, indent=2, ensure_ascii=False), encoding='utf-8')
        return parsed, metadata

    def generate(self, instructions, data, schema):
        attempted_errors = {}
        for target_model in self.models:
            try:
                parsed, metadata = self._call_model(target_model, instructions, data, schema)
                metadata['fallback_chain'] = self.models
                metadata['attempted_models'] = list(attempted_errors.keys()) + [target_model]
                metadata['fallback_occurred'] = len(attempted_errors) > 0
                if attempted_errors:
                    metadata['prior_errors'] = attempted_errors
                return parsed, metadata
            except Exception as error:
                attempted_errors[target_model] = str(error)
                if not self.auto_fallback:
                    raise

        error_summary = '; '.join(f"[{m}: {err}]" for m, err in attempted_errors.items())
        raise RuntimeError(f"All Gemini fallback models ({', '.join(self.models)}) failed: {error_summary}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--key-file')
    parser.add_argument('--model', default='auto')
    args = parser.parse_args()
    try:
        answer, meta = Gemini(args.model, args.key_file).generate(
            'Return the requested JSON.',
            {'request': 'Set ok to true.'},
            {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}
        )
        print(json.dumps({'connection': answer, 'model': meta['model'], 'model_version': meta['model_version'], 'attempted': meta.get('attempted_models')}))
    except Exception as error:
        print(str(error))
        raise SystemExit(1)
