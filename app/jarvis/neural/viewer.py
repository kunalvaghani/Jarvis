"""Live neuron view: a small local web page that reads the brain journal (read-only, 127.0.0.1 only).

Why not Electron/React (user question 1.3, 2026-11-02): an Electron shell keeps its own Chromium running (roughly
150-300 MB) next to the Chrome Jarvis already drives, which works against "never slow Jarvis". This page gives the
same rendering in the browser the user already has and costs nothing while it is closed.

Every lit neuron and moving signal comes from a journaled signal row (``/api/signals``): there are no decorative
activations. Payloads are never served: only signal types, neuron ids, redacted notes and verified statistics.
The view cannot run, approve or stop anything; stopping stays in the Jarvis island where the cancel signal lives.

    python -m jarvis.neural viewer        # prints the local address
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .journal import Journal

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Jarvis brain</title>
<script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
<style>
body{margin:0;font:13px system-ui,Segoe UI,sans-serif;background:#0b0f17;color:#d8e1f0;display:flex;height:100vh}
#side{width:330px;padding:12px;overflow:auto;border-right:1px solid #1d2636}#cy{flex:1}
h1{font-size:15px;margin:0 0 8px}h2{font-size:13px;margin:14px 0 6px;color:#8fb3ff}
.goal{padding:6px;border-radius:6px;cursor:pointer;margin:2px 0;background:#121a28}.goal:hover{background:#1a2538}
.sig{font-family:Consolas,monospace;font-size:11px;padding:2px 0;border-bottom:1px solid #151d2b}
.k-verified,.k-neuron\.succeeded,.k-verification\.passed{color:#6fe39b}.k-neuron\.failed,.k-goal\.failed,
.k-verification\.failed,.k-neuron\.blocked{color:#ff7b7b}.k-approval\.needed{color:#ffd166}
pre{white-space:pre-wrap;font-size:11px;background:#121a28;padding:8px;border-radius:6px}
</style></head><body><div id="side"><h1>Jarvis brain</h1><div id="stats"></div>
<h2>Goals</h2><div id="goals"></div><h2>Neuron</h2><pre id="neuron">Click a neuron.</pre>
<h2>Signals</h2><div id="sigs"></div></div><div id="cy"></div>
<script>
const color={sensor:'#5ab0ff',model:'#c792ea',tool:'#82aaff',mcp:'#89ddff',memory:'#f78c6c',skill:'#c3e88d',
 workflow:'#ffcb6b',verifier:'#ff5370',route:'#ffd166'};
let cy=null,goal=null,after=0;
async function j(u){const r=await fetch(u);return r.json()}
async function graph(){const g=await j('/api/graph'+(goal?'?goal='+goal:''));
 document.getElementById('stats').textContent=`graph v${g.version}: ${g.total_neurons} neurons, ${g.total_synapses} synapses (showing ${g.nodes.length})`;
 const els=g.nodes.map(n=>({data:{id:n.id,label:n.id.replace(/@v\d+$/,''),kind:n.kind}}))
  .concat(g.edges.map(e=>({data:{id:e.id,source:e.source,target:e.target,label:e.type,mode:e.mode}})));
 if(cy)cy.destroy();
 cy=cytoscape({container:document.getElementById('cy'),elements:els,layout:{name:'cose',animate:false},
  style:[{selector:'node',style:{'background-color':e=>color[e.data('kind')]||'#999',label:'data(label)',color:'#cfd8e8',
   'font-size':8,width:14,height:14}},{selector:'edge',style:{width:1,'line-color':'#2b3a55','target-arrow-shape':'triangle',
   'target-arrow-color':'#2b3a55','curve-style':'bezier'}},{selector:'edge[mode="feedback"]',style:{'line-style':'dashed',
   'line-color':'#ff5370','target-arrow-color':'#ff5370'}},{selector:'.fired',style:{'border-width':4,'border-color':'#ffffff'}},
   {selector:'.ok',style:{'background-color':'#6fe39b'}},{selector:'.bad',style:{'background-color':'#ff5370'}},
   {selector:'.wait',style:{'background-color':'#ffd166'}}]});
 cy.on('tap','node',async ev=>{const n=await j('/api/neuron?id='+encodeURIComponent(ev.target.id()));
  document.getElementById('neuron').textContent=JSON.stringify(n,null,1)});}
async function goals(){const g=await j('/api/goals');document.getElementById('goals').innerHTML=g.map(x=>
 `<div class="goal" onclick="pick('${x.goal_id}')"><b>${x.state}</b> ${x.goal_id}<br>${x.text.slice(0,90)}</div>`).join('')}
async function pick(id){goal=id;after=0;document.getElementById('sigs').innerHTML='';await graph();}
async function tick(){const s=await j('/api/signals?after='+after+(goal?'&goal='+goal:''));
 for(const x of s){after=Math.max(after,x.seq);const d=document.createElement('div');d.className='sig k-'+x.type;
  d.textContent=`${x.timestamp_utc.slice(11,19)} ${x.type} ${x.task_id||''} ${(x.target_node||x.source_node||'').replace(/@v\d+$/,'')} ${x.note||''}`;
  document.getElementById('sigs').prepend(d);const id=x.target_node||x.source_node;
  if(cy&&id){const n=cy.getElementById(id);if(n.length){n.removeClass('ok bad wait');n.addClass('fired');
   if(/succeeded|passed/.test(x.type))n.addClass('ok');if(/failed|blocked|denied/.test(x.type))n.addClass('bad');
   if(/approval.needed/.test(x.type))n.addClass('wait');setTimeout(()=>n.removeClass('fired'),900)}}}}
graph();goals();setInterval(tick,1000);setInterval(goals,5000);
</script></body></html>"""


def graph_view(journal: Journal, goal: Optional[str] = None, limit: int = 120) -> Dict[str, Any]:
    """The neighbourhood that matters now: a goal's fired neurons plus one hop, or the wired core."""
    snap = journal.graph()
    if snap is None:
        return {'version': 0, 'nodes': [], 'edges': [], 'total_neurons': 0, 'total_synapses': 0}
    neurons = {n['node_id']: n for n in snap['neurons']}
    synapses = snap['synapses']
    if goal:
        fired = {s.get('target_node') or s.get('source_node') for s in journal.signals(goal, limit=2000)}
        focus = {str(f) for f in fired if f in neurons}
        near = focus | {s['target'] for s in synapses if s['source'] in focus} | \
            {s['source'] for s in synapses if s['target'] in focus}
    else:
        near = {s['source'] for s in synapses} | {s['target'] for s in synapses}
    keep = sorted(near)[:limit]
    kept = set(keep)
    return {'version': snap['version'], 'total_neurons': len(neurons), 'total_synapses': len(synapses),
            'nodes': [{'id': i, 'kind': neurons[i]['kind']} for i in keep],
            'edges': [{'id': s['edge_id'], 'source': s['source'], 'target': s['target'], 'type': s['data_type'],
                       'mode': s['mode']} for s in synapses if s['source'] in kept and s['target'] in kept]}


def neuron_view(journal: Journal, node_id: str) -> Dict[str, Any]:
    snap = journal.graph() or {'neurons': [], 'synapses': []}
    neuron = next((n for n in snap['neurons'] if n['node_id'] == node_id), None)
    if neuron is None:
        return {'error': 'unknown neuron'}
    last = [s for s in journal.rows('SELECT body FROM signals WHERE body LIKE ? ORDER BY seq DESC LIMIT 5',
                                    (f'%{node_id}%',))]
    return {'contract': {k: neuron.get(k) for k in ('node_id', 'kind', 'capability', 'provider', 'inputs', 'outputs',
                                                    'side_effect_class', 'privilege', 'privacy', 'status',
                                                    'requirements', 'description')},
            'sends_to': [s['target'] for s in snap['synapses'] if s['source'] == node_id][:20],
            'receives_from': [s['source'] for s in snap['synapses'] if s['target'] == node_id][:20],
            'verified_stats': [r for r in journal.stats() if r['node_id'] == node_id],
            'last_signals': [{k: v for k, v in json.loads(r['body']).items() if k in ('type', 'goal_id', 'task_id',
                                                                                     'timestamp_utc', 'note')}
                             for r in last]}


class Handler(BaseHTTPRequestHandler):
    journal: Journal

    def log_message(self, *args: Any) -> None:
        return

    def _send(self, body: Any, kind: str = 'application/json') -> None:
        data = body.encode('utf-8') if isinstance(body, str) else json.dumps(body, default=str).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == '/':
            return self._send(PAGE, 'text/html')
        if url.path == '/api/graph':
            return self._send(graph_view(self.journal, q.get('goal')))
        if url.path == '/api/goals':
            return self._send(self.journal.rows('SELECT goal_id, text, state, stop_reason, updated FROM goals '
                                                'ORDER BY updated DESC LIMIT 30'))
        if url.path == '/api/signals':
            after = int(q.get('after', '0') or 0)
            return self._send(self.journal.signals(q.get('goal'), after=after, limit=200))
        if url.path == '/api/neuron':
            return self._send(neuron_view(self.journal, q.get('id', '')))
        self.send_error(404)


def serve(journal_path: Optional[Path] = None, port: int = 0) -> Tuple[ThreadingHTTPServer, str]:
    """Start the view on 127.0.0.1 in a daemon thread. Returns (server, address)."""
    journal = Journal(journal_path)
    handler = type('BoundHandler', (Handler,), {'journal': journal})
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=server.serve_forever, daemon=True, name='brain-viewer').start()
    return server, f'http://127.0.0.1:{server.server_address[1]}/'
