"""Local browser playground for the v3 deterministic response guardrail."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re

from run_gemini import STYLE_VERSION, handoff_draft
from support_system import risk_reason


INTENTS = (
    "billing_subscription", "account_access_security", "playback_app",
    "library_playlists", "catalog_availability", "feedback_feature_request",
    "social_acknowledgement", "other_unclear",
)


def suggest_intent(message):
    text = message.casefold()
    rules = (
        ("billing_subscription", r"\b(?:charg|refund|premium|subscription|payment|bill)"),
        ("account_access_security", r"\b(?:password|log ?in|account|email|hack|stolen)"),
        ("feedback_feature_request", r"\b(?:please add|bring back|feature|should add|release an app|wish|suggest)"),
        ("catalog_availability", r"\b(?:missing (?:song|album|artist)|not available|availability|catalog)"),
        ("library_playlists", r"\b(?:playlist|library|saved songs?|liked songs?)"),
        ("playback_app", r"\b(?:crash|lag|buffer|pause|play|volume|app|device|offline)"),
        ("social_acknowledgement", r"\b(?:thank|thanks|finally (?:have|got) access|works now|fixed now)"),
    )
    for intent, pattern in rules:
        if re.search(pattern, text):
            return intent
    return "other_unclear"


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>V3 response playground</title><style>
body{font:16px system-ui;margin:0;background:#f4f7fb;color:#18212f}.wrap{max-width:880px;margin:40px auto;padding:0 20px}
.card{background:white;border:1px solid #dce3ec;border-radius:16px;padding:24px;box-shadow:0 8px 30px #20304012}
textarea{box-sizing:border-box;width:100%;min-height:130px;padding:14px;border:1px solid #aeb9c8;border-radius:10px;font:inherit}
select,button{font:inherit;padding:10px 14px;border-radius:9px}select{border:1px solid #aeb9c8;background:white}button{border:0;background:#1db954;color:white;font-weight:700;cursor:pointer}
.row{display:flex;gap:12px;align-items:center;margin-top:14px}.result{margin-top:22px;padding:18px;background:#f7faf8;border-left:5px solid #1db954;border-radius:8px}.meta{display:grid;grid-template-columns:110px 1fr;gap:8px;margin-bottom:14px}.draft{font-size:18px;line-height:1.5}
.note{color:#5c6878;font-size:14px}code{word-break:break-word}@media(max-width:600px){.row{align-items:stretch;flex-direction:column}.meta{grid-template-columns:1fr}}
</style></head><body><main class="wrap"><h1>V3 response playground</h1><p class="note">Tests the deterministic safe-response layer locally. No message is sent to Gemini or the internet.</p>
<section class="card"><label for="message"><strong>Customer message</strong></label><textarea id="message" placeholder="Example: You charged me twice and I need a refund"></textarea>
<div class="row"><label>Intent <select id="intent"><option value="auto">Detect locally</option>__OPTIONS__</select></label><button id="run">Draft response</button></div>
<div id="result" class="result" hidden><div class="meta"><strong>Intent</strong><code id="outIntent"></code><strong>Route</strong><code id="route"></code><strong>Reason</strong><span id="reason"></span><strong>Version</strong><code id="version"></code></div><strong>Draft reply</strong><div class="draft" id="draft"></div></div></section></main>
<script>const q=s=>document.querySelector(s);q('#run').onclick=async()=>{const message=q('#message').value.trim();if(!message)return;const r=await fetch('/api/draft',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message,intent:q('#intent').value})});const x=await r.json();q('#outIntent').textContent=x.intent;q('#route').textContent=x.route;q('#reason').textContent=x.reason;q('#version').textContent=x.style_version;q('#draft').textContent=x.draft;q('#result').hidden=false};</script></body></html>"""
HTML = HTML.replace("__OPTIONS__", "".join(f'<option value="{x}">{x}</option>' for x in INTENTS))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404); return
        body = HTML.encode()
        self.send_response(200); self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/draft":
            self.send_error(404); return
        size = min(int(self.headers.get("content-length", "0")), 10000)
        data = json.loads(self.rfile.read(size))
        message = str(data.get("message", "")).strip()[:2000]
        intent = data.get("intent")
        if intent == "auto" or intent not in INTENTS:
            intent = suggest_intent(message)
        example = {"message": message, "context_status": {}}
        reason = risk_reason(example, intent) or "No verified historical evidence in this manual preview."
        result = {"intent": intent, "route": "escalate", "reason": reason,
                  "draft": handoff_draft(example, intent, reason), "style_version": STYLE_VERSION}
        body = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print("V3 response playground: http://127.0.0.1:8766", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
