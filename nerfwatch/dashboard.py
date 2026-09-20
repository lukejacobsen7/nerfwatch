"""Single-file HTML dashboard. Data is embedded as JSON; Chart.js from cdnjs."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from . import config
from .analyze import METRIC_DEFS, analyze
from .probes.suite import ORDER


def _payload(cfg: dict[str, Any], targets: list[str]) -> dict[str, Any]:
    out = []
    for t in targets:
        ta = analyze(t, cfg)
        runs = [
            {
                "id": m.run_id, "ts": m.ts, "label": dt.datetime.fromtimestamp(m.ts).strftime("%m-%d %H:%M"), "model": m.model, "quick": m.quick,
                **{k: getattr(m, k) for k, *_ in METRIC_DEFS}, "theta_se": m.theta_se, "by_family": m.by_family, "error_rate": m.error_rate, "hour": m.hour,
            }
            for m in ta.runs
        ]
        series = {k: {"label": s.label, "better": s.better, "alarm": (s.cusum.alarm_idx if s.cusum and s.cusum.alarmed else None), "direction": (s.cusum.direction if s.cusum else None), "mu0": (s.cusum.mu0 if s.cusum else None)} for k, s in ta.series.items()}
        out.append({"target": t, "runs": runs, "series": series, "alarms": ta.alarms, "verdict": ta.verdict, "baseline_n": ta.baseline_n})
    return {"generated": dt.datetime.now().isoformat(timespec="seconds"), "families": ORDER, "targets": out}


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>nerfwatch</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--bg:#f7f7f5;--fg:#141414;--muted:#6b6b6b;--card:#fff;--line:#e4e4e0;--ok:#1a7f4b;--bad:#c62828;--warn:#b26a00;--accent:#2BD9FF;--grid:#ececea}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1113;--fg:#ececec;--muted:#9a9a9a;--card:#171a1d;--line:#262a2e;--grid:#23272b;--ok:#3ddc84;--bad:#ff6b6b;--warn:#ffb74d}}
:root[data-theme=dark]{--bg:#0f1113;--fg:#ececec;--muted:#9a9a9a;--card:#171a1d;--line:#262a2e;--grid:#23272b;--ok:#3ddc84;--bad:#ff6b6b;--warn:#ffb74d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,Segoe UI,Roboto,sans-serif;padding:16px}
h1{font-size:22px;margin:0 0 4px}h1 code{color:var(--accent)}.sub{color:var(--muted);font-size:13px;margin-bottom:20px}
.target{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:20px}
.target h2{margin:0 0 6px;font-size:18px}.model{color:var(--muted);font-size:13px;margin-bottom:10px}
.verdict{padding:10px 12px;border-radius:8px;border:1px solid var(--line);margin-bottom:14px;font-weight:600}
.verdict.bad{border-color:var(--bad);color:var(--bad)}.verdict.ok{border-color:var(--ok);color:var(--ok)}.verdict.warn{border-color:var(--warn);color:var(--warn)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:14px}
.tile{border:1px solid var(--line);border-radius:8px;padding:8px 10px}.tile .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.tile .v{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}.tile .d{font-size:12px;color:var(--muted)}.tile.alarm{border-color:var(--warn)}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.chart{border:1px solid var(--line);border-radius:8px;padding:10px;min-height:220px}.chart h3{margin:0 0 6px;font-size:13px;color:var(--muted);font-weight:600}
canvas{max-height:200px}.alarms{font-size:13px;color:var(--warn);margin:6px 0 12px}.empty{color:var(--muted);font-style:italic}
</style></head><body>
<h1><code>&gt;_</code> nerfwatch</h1>
<div class="sub">is it getting dumber? generated __GEN__ · baseline = first N runs · alarms are CUSUM (k=0.5σ, h=4σ), not vibes</div>
<div id="app"></div>
<script>
const DATA=__DATA__;
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt={theta:v=>(v>=0?'+':'')+v.toFixed(2),accuracy:v=>Math.round(v*100)+'%',latency_ms:v=>Math.round(v)+'ms',reasoning_tokens:v=>Math.round(v),output_tokens:v=>Math.round(v),refusal_rate:v=>Math.round(v*100)+'%',lazy_rate:v=>Math.round(v*100)+'%',ident_logprob:v=>v.toFixed(2),ident_agree:v=>Math.round(v*100)+'%'};
const app=document.getElementById('app');
if(!DATA.targets.length){app.innerHTML='<p class="empty">no runs yet. run <code>nerfwatch run</code>.</p>'}
for(const t of DATA.targets){
  const el=document.createElement('section');el.className='target';
  const last=t.runs[t.runs.length-1];
  const vcls=/CHANGED|CUT|DROPPED|laziness|refusals/.test(t.verdict)?'bad':/stable/.test(t.verdict)?'ok':'warn';
  let tiles='';
  for(const [k,s] of Object.entries(t.series)){
    const base=t.runs.slice(0,t.baseline_n).map(r=>r[k]).filter(v=>v!=null);
    const b=base.length?base.reduce((a,c)=>a+c,0)/base.length:null;const v=last?last[k]:null;
    tiles+=`<div class="tile${s.alarm!=null?' alarm':''}"><div class="k">${s.label}</div><div class="v">${v==null?'–':fmt[k](v)}</div><div class="d">baseline ${b==null?'–':fmt[k](b)}${s.alarm!=null?' · ⚠ '+s.direction:''}</div></div>`;
  }
  el.innerHTML=`<h2>${t.target}</h2><div class="model">${last&&last.model?last.model:''} · ${t.runs.length} runs</div>
  <div class="verdict ${vcls}">${t.verdict}</div>${t.alarms.length?'<div class="alarms">'+t.alarms.map(a=>'⚠ '+a).join('<br>')+'</div>':''}
  <div class="tiles">${tiles}</div><div class="charts"></div>`;
  app.appendChild(el);
  const charts=el.querySelector('.charts');
  const labels=t.runs.map(r=>r.label);
  const mk=(title,datasets,opts={})=>{const d=document.createElement('div');d.className='chart';d.innerHTML=`<h3>${title}</h3><canvas></canvas>`;charts.appendChild(d);
    new Chart(d.querySelector('canvas'),{type:'line',data:{labels,datasets},options:{animation:false,responsive:true,plugins:{legend:{display:datasets.length>1,labels:{color:css('--muted'),boxWidth:10}}},scales:{x:{ticks:{color:css('--muted'),maxTicksLimit:8},grid:{color:css('--grid')}},y:{ticks:{color:css('--muted')},grid:{color:css('--grid')},...(opts.y||{})}},elements:{point:{radius:3},line:{tension:.25}}}});};
  const line=(k,color)=>({label:t.series[k]?t.series[k].label:k,data:t.runs.map(r=>r[k]),borderColor:color,backgroundColor:color,spanGaps:true,pointStyle:t.runs.map((r,i)=>t.series[k]&&t.series[k].alarm===i?'triangle':'circle'),pointRadius:t.runs.map((r,i)=>t.series[k]&&t.series[k].alarm===i?7:3)});
  const baseLine=k=>({label:'baseline',data:t.runs.map(_=>t.series[k]&&t.series[k].mu0!=null?(['latency_ms','reasoning_tokens','output_tokens'].includes(k)?Math.exp(t.series[k].mu0)-1:t.series[k].mu0):null),borderColor:css('--muted'),borderDash:[4,4],pointRadius:0,borderWidth:1});
  if(t.series.theta) mk('ability θ (Rasch, higher = smarter)',[line('theta',css('--accent')),baseLine('theta'),{label:'±1 se',data:t.runs.map(r=>r.theta!=null?r.theta+r.theta_se:null),borderColor:'transparent',backgroundColor:css('--accent')+'22',fill:'+1',pointRadius:0},{label:'',data:t.runs.map(r=>r.theta!=null?r.theta-r.theta_se:null),borderColor:'transparent',pointRadius:0}]);
  if(t.series.accuracy) mk('accuracy',[line('accuracy',css('--ok')),baseLine('accuracy')],{y:{min:0,max:1}});
  const pal=['#2BD9FF','#3ddc84','#ffb74d','#ff6b6b','#b39ddb','#4dd0e1','#f48fb1'];
  mk('accuracy by family',DATA.families.map((f,i)=>({label:f,data:t.runs.map(r=>r.by_family[f]),borderColor:pal[i%pal.length],backgroundColor:pal[i%pal.length],spanGaps:true,pointRadius:2})),{y:{min:0,max:1}});
  if(t.series.latency_ms) mk('latency ms (median per run)',[line('latency_ms',css('--warn')),baseLine('latency_ms')]);
  if(t.series.reasoning_tokens) mk('reasoning tokens (median) · the "juice" meter',[line('reasoning_tokens','#b39ddb'),baseLine('reasoning_tokens')]);
  if(t.series.output_tokens) mk('output tokens (median)',[line('output_tokens','#4dd0e1'),baseLine('output_tokens')]);
  if(t.series.refusal_rate||t.series.lazy_rate) mk('refusal rate · lazy rate',[line('refusal_rate',css('--bad')),line('lazy_rate','#f48fb1')],{y:{min:0,max:1}});
  if(t.series.ident_logprob) mk('identity: mean top-5 logprob (flat = same model)',[line('ident_logprob','#4dd0e1'),baseLine('ident_logprob')]);
  if(t.series.ident_agree) mk('identity: top-token agreement with baseline',[line('ident_agree','#b39ddb')],{y:{min:0,max:1}});
}
</script></body></html>
"""


def write(cfg: dict[str, Any], targets: list[str], path: Path | None = None) -> Path:
    path = path or (config.home() / "dashboard.html")
    payload = _payload(cfg, targets)
    html = TEMPLATE.replace("__DATA__", json.dumps(payload).replace("</", "<\\/")).replace("__GEN__", payload["generated"])
    path.write_text(html)
    return path
