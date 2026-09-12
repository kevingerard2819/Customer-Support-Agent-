import http from 'node:http';
import { readFile, writeFile, rename } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = dirname(dirname(fileURLToPath(import.meta.url)));
const args = Object.fromEntries(process.argv.slice(2).map((value, index, all) => value.startsWith('--') ? [value.slice(2), all[index + 1]] : null).filter(Boolean));
const packetPath = args.packet || join(repo, 'annotations', 'reply-review-packet-v2.json');
const ratingsPath = args.ratings || join(repo, 'annotations', 'reply-ratings-human-v2.json');
const port = Number(args.port || 8765);
const title = args.title || 'Reply quality review v2';
const packet = JSON.parse(await readFile(packetPath, 'utf8'));
const ids = new Set(packet.items.map(x => x.rating_id));
const dims = ['correctness', 'grounding', 'usefulness', 'routing_privacy'];

async function ratings() {
  try { return JSON.parse(await readFile(ratingsPath, 'utf8')); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    return { packet_id: packet.packet_id, rubric_version: 'v1', source: 'human_entries_in_local_browser_tool', ratings: {} };
  }
}

async function saveRating(value) {
  if (!ids.has(value.rating_id)) throw new Error('Unknown rating ID');
  for (const key of dims) if (![0, 1, 2].includes(value[key])) throw new Error(`${key} must be 0, 1 or 2`);
  if (typeof value.critical_failure !== 'boolean') throw new Error('Critical failure is required');
  const doc = await ratings();
  if (doc.packet_id !== packet.packet_id) throw new Error('Packet mismatch');
  doc.ratings[value.rating_id] = { ...Object.fromEntries(dims.map(k => [k, value[k]])), critical_failure: value.critical_failure,
    notes: String(value.notes || ''), updated_at: new Date().toISOString() };
  const temp = ratingsPath + '.tmp';
  await writeFile(temp, JSON.stringify(doc, null, 2) + '\n', 'utf8');
  await rename(temp, ratingsPath);
  return doc;
}

const page = String.raw`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title><style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#16202a;background:#eef2f6}*{box-sizing:border-box}body{margin:0}.top{position:sticky;top:0;background:white;border-bottom:1px solid #ccd5df;padding:14px 20px;z-index:2}.title{display:flex;justify-content:space-between;align-items:center}.title h1{font-size:22px;margin:0}.status{font-weight:700;color:#315b9d}.note{font-size:13px;color:#586675;margin-top:5px}.rating{display:grid;grid-template-columns:180px repeat(3,68px) 1fr;gap:5px;align-items:center;margin-top:10px}.rating strong{font-size:14px}.rating .hint{color:#647382;font-size:13px}.choice input{position:absolute;opacity:0}.choice span{display:block;text-align:center;padding:8px;border:2px solid #b7c2ce;border-radius:7px;cursor:pointer;font-weight:700}.choice input:checked+span{background:#1967d2;color:white;border-color:#1967d2}.critical{display:flex;gap:10px;align-items:center;margin-top:9px}.critical .choice span{min-width:70px}.actions{display:flex;gap:8px;margin-top:10px}.actions button{padding:10px 18px;border:1px solid #9aa8b6;background:white;border-radius:7px;font-weight:700;cursor:pointer}.actions .primary{background:#16794b;color:white;border-color:#16794b;font-size:15px}.actions .primary:hover{background:#10643d}.notes{flex:1;padding:9px;border:1px solid #aeb9c5;border-radius:6px}.card{max-width:1060px;margin:16px auto;background:white;padding:22px;border-radius:10px;box-shadow:0 2px 10px #1b2a3a18}.section{margin:18px 0}.section h2{font-size:13px;letter-spacing:.06em;color:#526171;margin:0 0 7px}.section p,.context,.evidence{white-space:pre-wrap;font-size:16px;line-height:1.5;margin:0}.draft{font-size:18px!important;background:#f3f8ff;border-left:4px solid #3578d4;padding:14px}.route{font-weight:700}.evidence{background:#f7f7f7;padding:12px;border-radius:6px;margin-bottom:10px}.error{color:#b42318;font-weight:700}@media(max-width:800px){.rating{grid-template-columns:130px repeat(3,55px)}.rating .hint{grid-column:1/-1}.top{position:static}}
</style></head><body><div class="top"><div class="title"><h1>${title}</h1><div id="status" class="status">Loading…</div></div>
<div class="note">Some drafts are intentionally weak baselines. Score exactly what you see; system names remain hidden.</div><div id="ratings"></div>
<div class="critical"><strong>Critical failure</strong><label class="choice"><input type="radio" name="critical" value="false"><span>No</span></label><label class="choice"><input type="radio" name="critical" value="true"><span>Yes</span></label><span class="hint">Yes only for fabricated actions/policy, public requests for private data, or missed required escalation.</span></div>
<div class="actions"><button id="prev">← Previous</button><button id="next">Next →</button><button id="unrated">Next unrated</button><input id="notes" class="notes" placeholder="Optional notes"><button id="save" class="primary">SAVE & NEXT</button></div><div id="error" class="error"></div></div>
<main class="card"><div class="section"><h2>CUSTOMER MESSAGE</h2><p id="message"></p></div><div class="section"><h2>EARLIER CONTEXT</h2><div id="context" class="context"></div></div><div class="section"><h2>DRAFT ROUTE</h2><p id="route" class="route"></p></div><div class="section"><h2>DRAFT REPLY</h2><p id="draft" class="draft"></p></div><div class="section"><h2>SUPPLIED HISTORICAL EVIDENCE</h2><div id="evidence"></div></div></main>
<script>
const dims=[['correctness','Correctness','0 wrong · 1 partly right · 2 correct'],['grounding','Grounding','0 unsupported · 1 weak · 2 supported'],['usefulness','Usefulness','0 no help · 1 partial · 2 useful'],['routing_privacy','Routing / privacy','0 unsafe · 1 uncertain · 2 appropriate']];
let packet,doc,index=0;const $=id=>document.getElementById(id);
$('ratings').innerHTML=dims.map(([k,n,h])=>'<div class="rating"><strong>'+n+'</strong>'+[0,1,2].map(v=>'<label class="choice"><input type="radio" name="'+k+'" value="'+v+'"><span>'+v+'</span></label>').join('')+'<span class="hint">'+h+'</span></div>').join('');
function complete(v){return v&&dims.every(([k])=>[0,1,2].includes(v[k]))&&typeof v.critical_failure==='boolean'}
function show(){const x=packet.items[index],v=doc.ratings[x.rating_id]||{};dims.forEach(([k])=>document.querySelectorAll('[name="'+k+'"]').forEach(e=>e.checked=String(v[k])===e.value));document.querySelectorAll('[name=critical]').forEach(e=>e.checked=String(v.critical_failure)===e.value);$('notes').value=v.notes||'';$('message').textContent=x.message;$('context').textContent=x.context.length?x.context.map(c=>c.role.toUpperCase()+': '+c.text).join('\n'):'No earlier context.';$('route').textContent=x.route;$('draft').textContent=x.draft;$('evidence').innerHTML=x.evidence.length?x.evidence.map(e=>'<div class="evidence"><b>Historical customer:</b> '+escapeHtml(e.customer_message)+'<br><b>Historical reply:</b> '+escapeHtml(e.historical_reply)+'</div>').join(''):'No historical evidence supplied.';update('Ready')}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function update(label){$('status').textContent=label+' · Item '+(index+1)+' / '+packet.items.length+' · '+Object.values(doc.ratings).filter(complete).length+' complete'}
function selected(){const out={rating_id:packet.items[index].rating_id,notes:$('notes').value};for(const [k] of dims){const e=document.querySelector('[name="'+k+'"]:checked');if(!e)return null;out[k]=Number(e.value)}const c=document.querySelector('[name=critical]:checked');if(!c)return null;out.critical_failure=c.value==='true';return out}
async function save(move=true){$('error').textContent='';const value=selected();if(!value){$('error').textContent='Choose 0, 1 or 2 on every row and choose Critical failure: No or Yes.';return}update('Saving…');const response=await fetch('/api/rating',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(value)});if(!response.ok){$('error').textContent=await response.text();update('NOT SAVED');return}doc=await response.json();if(move)index=Math.min(packet.items.length-1,index+1);show()}
$('save').onclick=()=>save(true);$('prev').onclick=()=>{index=Math.max(0,index-1);show()};$('next').onclick=()=>{index=Math.min(packet.items.length-1,index+1);show()};$('unrated').onclick=()=>{for(let n=1;n<=packet.items.length;n++){const i=(index+n)%packet.items.length;if(!complete(doc.ratings[packet.items[i].rating_id])){index=i;show();return}}};document.addEventListener('keydown',e=>{if(e.altKey&&e.key==='Enter')save(true)});
(async()=>{const state=await fetch('/api/state').then(r=>r.json());packet=state.packet;doc=state.ratings;const first=packet.items.findIndex(x=>!complete(doc.ratings[x.rating_id]));index=first<0?0:first;show()})().catch(e=>$('error').textContent=e.message);
</script></body></html>`;

const server=http.createServer(async (req,res)=>{
  try {
    if(req.method==='GET'&&req.url==='/'){res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store'});return res.end(page)}
    if(req.method==='GET'&&req.url==='/api/state'){res.writeHead(200,{'content-type':'application/json','cache-control':'no-store'});return res.end(JSON.stringify({packet,ratings:await ratings()}))}
    if(req.method==='POST'&&req.url==='/api/rating'){let body='';for await(const chunk of req){body+=chunk;if(body.length>100000)throw new Error('Request too large')}const doc=await saveRating(JSON.parse(body));res.writeHead(200,{'content-type':'application/json'});return res.end(JSON.stringify(doc))}
    res.writeHead(404);res.end('Not found');
  } catch(error){res.writeHead(400,{'content-type':'text/plain; charset=utf-8'});res.end(error.message)}
});
server.listen(port,'127.0.0.1',()=>console.log(`Reply review: http://127.0.0.1:${port}`));
