"""Run the real retrieval + Gemini + v3 gate pipeline for manual testing."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from gemini_client import Gemini
from run_gemini import INSTRUCTIONS, SCHEMA, STYLE_VERSION, gate
from sentiment import analyze_sentiment, tone_guidance
from support_system import Systems, privacy_redact


ROOT = Path(__file__).resolve().parents[1]


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Live Spotify support agent</title><style>
body{font:16px system-ui;margin:0;background:#f3f6fa;color:#18212f}.wrap{max-width:920px;margin:34px auto;padding:0 18px}
.card{background:#fff;border:1px solid #dce3ec;border-radius:16px;padding:24px;box-shadow:0 8px 30px #20304012}
textarea{box-sizing:border-box;width:100%;min-height:130px;padding:14px;border:1px solid #aeb9c8;border-radius:10px;font:inherit}
button{margin-top:13px;border:0;background:#1db954;color:#fff;font:inherit;font-weight:700;padding:11px 17px;border-radius:9px;cursor:pointer}
button:disabled{opacity:.55}.result{margin-top:22px;padding:18px;background:#f7faf8;border-left:5px solid #1db954;border-radius:8px}
.meta{display:grid;grid-template-columns:120px 1fr;gap:8px;margin-bottom:15px}.draft{font-size:18px;line-height:1.5}.note,.evidence{color:#5c6878;font-size:14px}
.error{border-color:#d33;background:#fff5f5}code{word-break:break-word}@media(max-width:600px){.meta{grid-template-columns:1fr}}
</style></head><body><main class="wrap"><h1>Live Spotify support agent</h1><p class="note">Real Gemini classification and drafting with historical retrieval and the v3 output gate. Messages are sent to Gemini for this test.</p>
<section class="card"><label><strong>Customer message</strong></label><textarea id="message" placeholder="Example: You charged me twice and I need help"></textarea><button id="run">Run complete agent</button>
<div id="result" class="result" hidden><div class="meta"><strong>Intent</strong><code id="intent"></code><strong>Route</strong><code id="route"></code><strong>Reason</strong><span id="reason"></span><strong>Model</strong><code id="model"></code><strong>Gate</strong><span id="gate"></span></div><strong>Draft reply</strong><div class="draft" id="draft"></div><p class="evidence" id="evidence"></p></div></section></main>
<script>const q=s=>document.querySelector(s);q('#run').onclick=async()=>{const message=q('#message').value.trim();if(!message)return;const b=q('#run'),box=q('#result');b.disabled=true;b.textContent='Running Gemini…';box.hidden=true;try{const r=await fetch('/api/agent',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message})});const x=await r.json();if(!r.ok)throw Error(x.error||'Request failed');box.classList.remove('error');q('#intent').textContent=x.intent;q('#route').textContent=x.route;q('#reason').textContent=x.reason;q('#model').textContent=x.model;q('#gate').textContent=x.output_check_violations.length?x.output_check_violations.join('; '):'passed unchanged';q('#draft').textContent=x.draft;q('#evidence').textContent='Historical evidence IDs: '+(x.evidence_ids.join(', ')||'none');box.hidden=false}catch(e){box.classList.add('error');box.innerHTML='<strong>Agent error</strong><p></p>';box.querySelector('p').textContent=e.message;box.hidden=false}finally{b.disabled=false;b.textContent='Run complete agent'}};</script></body></html>"""


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_agent(model, key_file):
    packet = read(ROOT / "annotations/batch-200.json")
    gold = read(ROOT / "annotations/golden-completed.json")
    history = read(ROOT / "data/retrieval/history.json")
    development = [row for row in packet["examples"] if row["split"] == "dev"]
    labels = {row["tweet_id"]: gold["labels"][row["tweet_id"]] for row in development}
    systems = Systems(development, labels, history)
    guide = (ROOT / "docs/annotation-guide.md").read_text(encoding="utf-8")
    instructions = INSTRUCTIONS + "\nGUIDE:\n" + guide
    cache = ROOT.parents[1] / "work" / "live-agent-cache"
    client = Gemini(model, key_file, cache)

    def run(message):
        example = {"tweet_id": "manual", "message": message, "context": [], "context_status": {}}
        evidence = systems.retrieve(example)
        sentiment = analyze_sentiment(message)
        data = {
            "message": privacy_redact(message), "context": [], "context_status": {},
            "historical_records": [
                dict(row, customer_message=privacy_redact(row["customer_message"]),
                     historical_reply=privacy_redact(row["historical_reply"]))
                for row in evidence
            ],
            "sentiment_signal": sentiment, "tone_guidance": tone_guidance(sentiment),
        }
        raw, metadata = client.generate(instructions, data, SCHEMA)
        result = gate(raw, example, evidence)
        return dict(result, model=metadata.get("model_version") or model,
                    retrieved_evidence_ids=[row["support_tweet_id"] for row in evidence])

    return run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    run_agent = build_agent(args.model, args.key_file)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/": self.send_error(404); return
            body = HTML.encode(); self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            if self.path != "/api/agent": self.send_error(404); return
            try:
                size = min(int(self.headers.get("content-length", "0")), 10000)
                message = str(json.loads(self.rfile.read(size)).get("message", "")).strip()[:2000]
                if not message: raise ValueError("Enter a customer message.")
                value, status = run_agent(message), 200
            except Exception as error:
                value, status = {"error": str(error)}, 502
            body = json.dumps(value, ensure_ascii=False).encode(); self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def log_message(self, *_): pass

    print(f"Live agent ({args.model}): http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
