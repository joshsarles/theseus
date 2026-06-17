"""APPRENTICE watch console — the operator surface for the PED demo (FE slot).

Stdlib only (http.server + json). Serves one page that draws the living target picture
from referee.ped_demo.build_picture(): tracks fuse over time, the convoy clusters into a
formation, the watch box is overlaid, and each watch-box entry shows as a DRAFT nomination
card with an Accept / Override control. The control is the human-in-command beat: nothing is
nominated unless the human acts. Drafts are advisory; the apprentice never decides.

Run:  python -m referee.console   (or `make console`), then open http://127.0.0.1:8800
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
from functools import partial

from .ped_demo import build_picture

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>APPRENTICE — watch console</title>
<style>
 :root{--bg:#0b0f14;--panel:#121a24;--ink:#cde3ff;--dim:#5b7088;--draft:#ffcc44;--accent:#36d1a0}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 ui-monospace,Menlo,monospace}
 header{padding:10px 16px;border-bottom:1px solid #1d2a38;display:flex;gap:16px;align-items:baseline}
 header b{color:#fff;font-size:16px} header .dim{color:var(--dim)}
 .wrap{display:flex;height:calc(100vh - 48px)}
 .map{flex:1;position:relative} svg{width:100%;height:100%}
 .side{width:340px;border-left:1px solid #1d2a38;padding:14px;overflow:auto}
 .card{background:var(--panel);border:1px solid #24344a;border-left:3px solid var(--draft);border-radius:8px;padding:10px;margin-bottom:10px}
 .card h4{margin:0 0 4px;color:var(--draft)} .card .meta{color:var(--dim);font-size:12px}
 .btns{margin-top:8px;display:flex;gap:8px}
 button{flex:1;padding:6px;border:1px solid #2c4055;border-radius:6px;background:#16202c;color:var(--ink);cursor:pointer}
 button:hover{border-color:var(--accent)} button.ovr:hover{border-color:#ff6b6b}
 .done{opacity:.5;border-left-color:var(--accent)}
 .legend{color:var(--dim);font-size:12px;margin-top:12px}
 .k{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:middle}
</style></head>
<body>
<header><b>APPRENTICE</b> <span class="dim">watch console — synthetic, unclassified stream. The fleet drafts; the human commands.</span></header>
<div class="wrap">
 <div class="map"><svg id="svg" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid meet"></svg></div>
 <div class="side"><div id="noms"></div>
   <div class="legend">
     <div><span class="k" style="background:#36d1a0"></span>moving track</div>
     <div><span class="k" style="background:#6aa0ff"></span>stationary track</div>
     <div><span class="k" style="background:#ffcc44"></span>nomination draft (watch box)</div>
     <div><span class="k" style="background:#39506b"></span>rejected clutter (no track)</div>
   </div>
 </div>
</div>
<script>
const SVG="http://www.w3.org/2000/svg";
function el(n,a){const e=document.createElementNS(SVG,n);for(const k in a)e.setAttribute(k,a[k]);return e;}
async function load(){
  const p=await (await fetch('/api/picture')).json();
  // bounds from all points + watch box, with margin
  let pts=[]; p.tracks.forEach(t=>t.dets.forEach(d=>pts.push(d))); (p.strays||[]).forEach(s=>pts.push(s));
  const wb=p.watch_box; pts.push({lat:wb.lat_min,lon:wb.lon_min},{lat:wb.lat_max,lon:wb.lon_max});
  const las=pts.map(d=>d.lat), los=pts.map(d=>d.lon);
  const laMin=Math.min(...las),laMax=Math.max(...las),loMin=Math.min(...los),loMax=Math.max(...los);
  const pad=0.12, W=1000;
  const sx=lo=>{const r=(lo-loMin)/((loMax-loMin)||1);return (pad+r*(1-2*pad))*W;};
  const sy=la=>{const r=(la-laMin)/((laMax-laMin)||1);return (pad+(1-r)*(1-2*pad))*W;}; // north up
  const svg=document.getElementById('svg'); svg.innerHTML='';
  // grid
  for(let i=0;i<=10;i++){const g=pad*W+i/10*(1-2*pad)*W;
    svg.appendChild(el('line',{x1:g,y1:pad*W,x2:g,y2:(1-pad)*W,stroke:'#16202c'}));
    svg.appendChild(el('line',{x1:pad*W,y1:g,x2:(1-pad)*W,y2:g,stroke:'#16202c'}));}
  // watch box
  const x1=sx(wb.lon_min),x2=sx(wb.lon_max),y1=sy(wb.lat_max),y2=sy(wb.lat_min);
  svg.appendChild(el('rect',{x:x1,y:y1,width:x2-x1,height:y2-y1,fill:'rgba(255,204,68,.06)',stroke:'#ffcc44',"stroke-dasharray":"6 4"}));
  svg.appendChild(el('text',{x:x1+4,y:y1+16,fill:'#ffcc44','font-size':12,'font-family':'monospace'})).textContent='WATCH';
  // clutter
  (p.strays||[]).forEach(s=>svg.appendChild(el('circle',{cx:sx(s.lon),cy:sy(s.lat),r:3,fill:'#39506b'})));
  // tracks
  const fcol=['#36d1a0','#9b7bff','#ff9f43'];
  p.tracks.forEach(t=>{
    const col = t.kind==='moving' ? (t.formation!=null?fcol[t.formation%fcol.length]:'#36d1a0') : '#6aa0ff';
    const pathPts=t.dets.map(d=>sx(d.lon)+','+sy(d.lat)).join(' ');
    svg.appendChild(el('polyline',{points:pathPts,fill:'none',stroke:col,'stroke-width':2,'stroke-opacity':.8}));
    t.dets.forEach((d,i)=>svg.appendChild(el('circle',{cx:sx(d.lon),cy:sy(d.lat),r:i===t.dets.length-1?5:2.5,fill:col})));
    const last=t.dets[t.dets.length-1];
    svg.appendChild(el('text',{x:sx(last.lon)+8,y:sy(last.lat)-8,fill:col,'font-size':12,'font-family':'monospace'})).textContent=t.id+(t.formation!=null?' [F'+t.formation+']':'');
  });
  // nominations on map
  p.nominations.forEach(n=>{
    const c=el('circle',{cx:sx(n.lon),cy:sy(n.lat),r:11,fill:'none',stroke:'#ffcc44','stroke-width':2});
    svg.appendChild(c);
  });
  // nomination cards
  const box=document.getElementById('noms'); box.innerHTML='';
  if(!p.nominations.length){box.innerHTML='<div class="meta">No track has entered the watch box. Nothing drafted. (Correct: no false nomination.)</div>';}
  p.nominations.forEach((n,i)=>{
    const d=document.createElement('div'); d.className='card';
    d.innerHTML=`<h4>DRAFT nomination · ${n.track_id}</h4>
      <div class="meta">watch-box entry ${n.ts}<br>loc ${n.lat.toFixed(4)}, ${n.lon.toFixed(4)} · conf ${n.confidence}</div>
      <div class="btns"><button>Accept</button><button class="ovr">Override</button></div>`;
    const [acc,ovr]=d.querySelectorAll('button');
    acc.onclick=()=>{d.classList.add('done');d.querySelector('h4').textContent='ACCEPTED by human · '+n.track_id;};
    ovr.onclick=()=>{d.classList.add('done');d.querySelector('h4').textContent='OVERRIDDEN by human · '+n.track_id;};
    box.appendChild(d);
  });
}
load();
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/picture"):
            self._send(200, json.dumps(build_picture()).encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *args) -> None:  # quiet
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="APPRENTICE watch console (stdlib).")
    ap.add_argument("--port", type=int, default=8800)
    args = ap.parse_args(argv)
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"APPRENTICE console on http://127.0.0.1:{args.port}  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
