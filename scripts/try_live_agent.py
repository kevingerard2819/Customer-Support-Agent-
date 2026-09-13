"""Run the real retrieval + Gemini + v3/v4 gate pipeline with auto-model fallback for manual testing."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from gemini_client import Gemini, DEFAULT_FALLBACK_CHAIN
from run_gemini import INSTRUCTIONS, SCHEMA, STYLE_VERSION, gate
from sentiment import analyze_sentiment, tone_guidance
from support_system import Systems, privacy_redact


ROOT = Path(__file__).resolve().parents[1]


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Live Spotify support agent — Auto Model Selection</title><style>
body{font:16px system-ui;margin:0;background:#f3f6fa;color:#18212f}.wrap{max-width:920px;margin:34px auto;padding:0 18px}
.card{background:#fff;border:1px solid #dce3ec;border-radius:16px;padding:24px;box-shadow:0 8px 30px #20304012}
textarea,input,select{box-sizing:border-box;width:100%;padding:14px;border:1px solid #aeb9c8;border-radius:10px;font:inherit}textarea{min-height:130px}label{display:block;margin-top:13px}
button{margin-top:16px;border:0;background:#1db954;color:#fff;font:inherit;font-weight:700;padding:12px 20px;border-radius:9px;cursor:pointer}
button:disabled{opacity:.55}.result{margin-top:22px;padding:18px;background:#f7faf8;border-left:5px solid #1db954;border-radius:8px}
.meta{display:grid;grid-template-columns:130px 1fr;gap:8px;margin-bottom:15px}.draft{font-size:18px;line-height:1.5}.note,.evidence{color:#5c6878;font-size:14px}
.error{border-color:#d33;background:#fff5f5}.live{display:inline-block;background:#fff3cd;color:#674d00;border:1px solid #e7cc7a;border-radius:7px;padding:9px 12px;font-weight:700}
.badge{display:inline-block;background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7;border-radius:6px;padding:4px 8px;font-size:13px;font-weight:600}
.badge.fallback{background:#fff8e1;color:#b78103;border-color:#ffe082}
code{word-break:break-word}@media(max-width:600px){.meta{grid-template-columns:1fr}}
</style></head><body><main class="wrap"><h1>Live Spotify support agent</h1><p class="note">Real Gemini classification and drafting with historical retrieval, automatic model fallback (3.8 → 3.7 → 3.6 → 3.5 → 2.5), and deterministic output safety gate.</p>
<p class="live">LIVE GEMINI API: the customer message and retrieved historical snippets are sent to Google Gemini.</p>
<section class="card">
<label><strong>Model Selection & Fallback Strategy</strong></label>
<select id="model">
  <option value="auto" selected>Auto Fallback (gemini-3.8 → 3.7 → 3.6 → 3.5 → 2.5) [Recommended]</option>
  <option value="gemini-3.8-flash">Gemini 3.8 Flash (with auto-fallback on error)</option>
  <option value="gemini-3.7-flash">Gemini 3.7 Flash (with auto-fallback on error)</option>
  <option value="gemini-3.6-flash">Gemini 3.6 Flash (with auto-fallback on error)</option>
  <option value="gemini-3.5-flash">Gemini 3.5 Flash (with auto-fallback on error)</option>
  <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
</select>
<label><strong>Gemini API key</strong></label><input id="key" type="password" autocomplete="off" placeholder="Required once; kept only in this local server's memory"><p class="note">The key is never written to disk, displayed, or included in the repository.</p>
<label><strong>Customer message</strong></label><textarea id="message" placeholder="Example: You charged me twice and I need help"></textarea>
<button id="run">Run complete agent</button>
<div id="result" class="result" hidden>
  <div class="meta">
    <strong>Intent</strong><code id="intent"></code>
    <strong>Route</strong><code id="route"></code>
    <strong>Reason</strong><span id="reason"></span>
    <strong>Model Used</strong><div><code id="model_used"></code> <span id="fallback_badge"></span></div>
    <strong>Gate Check</strong><span id="gate"></span>
  </div>
  <strong>Draft reply</strong><div class="draft" id="draft"></div>
  <p class="evidence" id="evidence"></p>
</div>
</section></main>
<script>
const q=s=>document.querySelector(s);
let hasKey=false;
q('#run').onclick=async()=>{
  const message=q('#message').value.trim(),api_key=q('#key').value.trim(),model=q('#model').value;
  if(!message)return;
  const b=q('#run'),box=q('#result'),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),90000);
  b.disabled=true;b.textContent='Contacting Gemini (auto-fallback enabled)…';box.hidden=true;
  try{
    const r=await fetch('/api/agent',{
      method:'POST',
      headers:{'content-type':'application/json'},
      body:JSON.stringify({message,api_key,model}),
      signal:controller.signal
    });
    const x=await r.json();
    if(!r.ok)throw Error(x.error||'Request failed');
    hasKey=true;
    q('#key').value='';
    q('#key').placeholder='Configured in server memory';
    box.classList.remove('error');
    q('#intent').textContent=x.intent;
    q('#route').textContent=x.route;
    q('#reason').textContent=x.reason;
    q('#model_used').textContent=x.model;
    const badge=q('#fallback_badge');
    if(x.fallback_occurred){
      badge.className='badge fallback';
      badge.textContent='Auto-fallback from: '+(x.attempted_models?x.attempted_models.slice(0,-1).join(', '):'primary');
    } else {
      badge.className='badge';
      badge.textContent='Direct response';
    }
    q('#gate').textContent=x.output_check_violations&&x.output_check_violations.length?x.output_check_violations.join('; '):'passed unchanged';
    q('#draft').textContent=x.draft;
    q('#evidence').textContent='Historical evidence IDs: '+((x.evidence_ids&&x.evidence_ids.join(', '))||'none');
    box.hidden=false;
  }catch(e){
    box.classList.add('error');
    box.innerHTML='<strong>Agent error</strong><p></p>';
    box.querySelector('p').textContent=e.name==='AbortError'?'Gemini did not respond within 90 seconds across all fallback models. Check quota or network connection.':e.message;
    box.hidden=false;
  }finally{
    clearTimeout(timer);
    b.disabled=false;
    b.textContent='Run complete agent';
  }
};
</script></body></html>"""


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class LiveAgentServer:
    def __init__(self, default_model="auto", key_file=None):
        self.default_model = default_model
        self.key_file = key_file
        self.api_key = Path(key_file).read_text(encoding='utf-8').strip() if key_file and Path(key_file).exists() else None
        
        packet = read(ROOT / "annotations/batch-200.json")
        gold = read(ROOT / "annotations/golden-completed.json")
        history = read(ROOT / "data/retrieval/history.json")
        development = [row for row in packet["examples"] if row["split"] == "dev"]
        labels = {row["tweet_id"]: gold["labels"][row["tweet_id"]] for row in development}
        self.systems = Systems(development, labels, history)
        self.guide = (ROOT / "docs/annotation-guide.md").read_text(encoding="utf-8")
        self.instructions = INSTRUCTIONS + "\nGUIDE:\n" + self.guide
        self.cache = ROOT.parents[1] / "work" / "live-agent-cache"

    def run(self, message, model="auto", api_key=None):
        key = api_key or self.api_key
        if not key:
            raise ValueError("Enter a Gemini API key. It will be kept only in this server process memory.")
        if api_key:
            self.api_key = api_key

        model_spec = model if model and model != "auto" else self.default_model
        client = Gemini(
            model=model_spec,
            key_file=None,
            cache=self.cache,
            min_interval=0,
            api_key=key,
            request_timeout=35,
            max_attempts=2,
            auto_fallback=True
        )

        example = {"tweet_id": "manual", "message": message, "context": [], "context_status": {}}
        evidence = self.systems.retrieve(example)
        sentiment = analyze_sentiment(message)
        data = {
            "message": privacy_redact(message),
            "context": [],
            "context_status": {},
            "historical_records": [
                dict(row, customer_message=privacy_redact(row["customer_message"]),
                     historical_reply=privacy_redact(row["historical_reply"]))
                for row in evidence
            ],
            "sentiment_signal": sentiment,
            "tone_guidance": tone_guidance(sentiment),
        }
        raw, metadata = client.generate(self.instructions, data, SCHEMA)
        result = gate(raw, example, evidence)
        return dict(
            result,
            model=metadata.get("model_version") or metadata.get("model") or model_spec,
            attempted_models=metadata.get("attempted_models", []),
            fallback_occurred=metadata.get("fallback_occurred", False),
            retrieved_evidence_ids=[row["support_tweet_id"] for row in evidence]
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    server_engine = LiveAgentServer(default_model=args.model, key_file=args.key_file)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            body = HTML.encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/api/agent":
                self.send_error(404)
                return
            try:
                size = min(int(self.headers.get("content-length", "0")), 10000)
                payload = json.loads(self.rfile.read(size))
                message = str(payload.get("message", "")).strip()[:2000]
                if not message:
                    raise ValueError("Enter a customer message.")
                api_key = str(payload.get("api_key", "")).strip() or None
                model = str(payload.get("model", "auto")).strip()
                value = server_engine.run(message=message, model=model, api_key=api_key)
                status = 200
            except Exception as error:
                value = {"error": str(error)}
                status = 502
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    print(f"Live agent with auto model selection ({args.model}): http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
