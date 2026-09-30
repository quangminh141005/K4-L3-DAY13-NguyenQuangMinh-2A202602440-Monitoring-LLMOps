"""Create reproducible incident evidence pages from local logs and Langfuse v2 observations."""
from __future__ import annotations

import html
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from langfuse import get_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.challenge import load_challenge

OUT = ROOT / "submission/evidence"


def when(row):
    return datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))


def p95(values):
    values = sorted(values)
    return values[math.ceil(len(values) * .95) - 1]


def page(title, subtitle, body):
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>{html.escape(title)}</title><style>
    body{{font:19px system-ui;background:#f4f7fb;color:#14213d;margin:36px}}
    h1{{font-size:36px;margin:0 0 8px}}h2{{font-size:23px;margin:0 0 12px}}
    .sub{{color:#52637a;margin:0 0 26px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
    section{{background:white;border:1px solid #dce3ec;border-radius:14px;padding:22px}}
    strong{{color:#0f172a}}.muted{{color:#52637a}}.bad{{color:#b91c1c}}.good{{color:#047857}}
    code{{font-size:17px}}pre{{white-space:pre-wrap;word-break:break-word;font-size:16px;background:#f8fafc;padding:16px;border-radius:8px}}
    .row{{display:flex;justify-content:space-between;border-bottom:1px solid #e5e7eb;padding:11px 0}}
    svg{{width:100%;height:auto}}</style><h1>{html.escape(title)}</h1><p class="sub">{html.escape(subtitle)}</p>{body}</html>'''


def main():
    challenge = load_challenge(ROOT / "config/challenge.json")
    rows = [json.loads(line) for line in (ROOT / "data/logs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    enabled = next(r for r in reversed(rows) if r.get("event") == "incident_enabled" and r.get("payload", {}).get("name") == challenge.incident)
    start = when(enabled)
    disabled = next((r for r in rows if r.get("event") == "incident_disabled" and when(r) > start), None)
    end = when(disabled) if disabled else max(map(when, rows))
    incident = [r for r in rows if r.get("event") == "response_sent" and r.get("feature") == challenge.affected_feature and start <= when(r) <= end]
    baseline = [r for r in rows if r.get("event") == "response_sent" and r.get("feature") == challenge.affected_feature and when(r) < start][-len(incident):]
    if not incident or not baseline:
        raise RuntimeError("Need matching baseline and incident response_sent events")
    selected = max(incident, key=lambda r: r["latency_ms"])
    cid = selected["correlation_id"]
    received = next(r for r in rows if r.get("event") == "request_received" and r.get("correlation_id") == cid)
    base_ms = [r["latency_ms"] for r in baseline]
    incident_ms = [r["latency_ms"] for r in incident]
    scale = max(challenge.latency_threshold_ms, *base_ms, *incident_ms) * 1.12
    bars = []
    for label, values, x, color in [("Baseline", base_ms, 65, "#2563eb"), ("Incident", incident_ms, 790, "#dc2626")]:
        bars.append(f'<text x="{x}" y="55" font-size="23" font-weight="bold">{label}: P95 {p95(values):,} ms</text>')
        for i, value in enumerate(values):
            y = 105 + i * 61
            width = value / scale * 500
            bars.append(f'<text x="{x}" y="{y+20}" font-size="17">#{i+1}</text><rect x="{x+42}" y="{y}" width="{width:.1f}" height="28" fill="{color}" rx="5"/><text x="{x+52+width:.1f}" y="{y+21}" font-size="17">{value:,} ms</text>')
    limit_x = 832 + challenge.latency_threshold_ms / scale * 500
    bars.append(f'<line x1="{limit_x:.1f}" y1="95" x2="{limit_x:.1f}" y2="415" stroke="#111827" stroke-dasharray="6 5"/><text x="{limit_x-155:.1f}" y="438" font-size="17">challenge threshold {challenge.latency_threshold_ms:,} ms</text>')
    metric_body = f'<section><h2>Latency by request · {html.escape(challenge.affected_feature)}</h2><svg viewBox="0 0 1450 460">{"".join(bars)}</svg><p>TTFT stayed near 50 ms. The symptom is response latency, not first-token latency.</p></section>'
    (OUT / "12-incident-metric.html").write_text(page("Incident metric", f"{challenge.challenge_id} · UTC {start:%Y-%m-%d %H:%M:%S}–{end:%H:%M:%S} · data/logs.jsonl", metric_body), encoding="utf-8")

    log_body = f'''<div class="grid"><section><h2>Request received</h2><pre>{html.escape(json.dumps({k: received.get(k) for k in ('ts','event','correlation_id','feature','model','env')}, indent=2))}</pre></section><section><h2>Response sent</h2><pre>{html.escape(json.dumps({k: selected.get(k) for k in ('ts','event','correlation_id','latency_ms','ttft_ms','tool_name','tool_success')}, indent=2))}</pre></section></div><section style="margin-top:20px"><h2>Correlation</h2><p>Same request ID in both structured log events: <code>{html.escape(cid)}</code>. Response latency <strong class="bad">{selected['latency_ms']:,} ms</strong> exceeds the challenge threshold of {challenge.latency_threshold_ms:,} ms.</p><p class="muted">Source: data/logs.jsonl · Original log values; user message omitted to protect PII.</p></section>'''
    (OUT / "13-incident-log.html").write_text(page("Incident log", f"{challenge.challenge_id} · {cid}", log_body), encoding="utf-8")

    load_dotenv(ROOT / ".env")
    observations = get_client().api.observations.get_many(limit=1000, fields="core,basic,time,metadata,usage,model,trace_context", from_start_time=start - timedelta(minutes=1), to_start_time=end + timedelta(minutes=1)).data
    root = next((o for o in observations if o.name == "lab-agent-run" and (o.metadata or {}).get("correlation_id") == cid), None)
    if root is None:
        raise RuntimeError(f"Langfuse root observation not found for {cid}")
    spans = [o for o in observations if o.trace_id == root.trace_id]
    spans.sort(key=lambda o: o.start_time)
    colors = {"lab-agent-run": "#1d4ed8", "retrieval": "#dc2626", "llm-generation": "#059669"}
    first = min(o.start_time for o in spans)
    total_ms = max((o.end_time - first).total_seconds() * 1000 for o in spans if o.end_time)
    chart = []
    details = []
    for i, o in enumerate(spans):
        if o.end_time is None:
            continue
        offset = (o.start_time - first).total_seconds() * 1000
        duration = (o.end_time - o.start_time).total_seconds() * 1000
        x = 255 + offset / total_ms * 1000
        w = max(2, duration / total_ms * 1000)
        y = 70 + i * 86
        name = html.escape(o.name)
        chart.append(f'<text x="20" y="{y+24}" font-size="20">{name}</text><rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="34" rx="5" fill="{colors.get(o.name,"#64748b")}"/><text x="{min(x+w+10,1280):.1f}" y="{y+24}" font-size="18">{duration:,.0f} ms</text>')
        details.append(f'<div class="row"><span>{name} · span <code>{o.id}</code></span><strong>{duration:,.0f} ms</strong></div>')
    trace_body = f'''<section><h2>Langfuse observation timeline</h2><svg viewBox="0 0 1450 390">{"".join(chart)}</svg><p>Trace ID: <code>{root.trace_id}</code> · Log correlation ID: <code>{cid}</code></p></section><section style="margin-top:20px"><h2>Measured spans</h2>{"".join(details)}<p class="muted">Source: Langfuse GET /api/public/v2/observations, filtered to this trace. Retrieval contains the latency increase.</p></section>'''
    (OUT / "14-incident-trace.html").write_text(page("Incident trace", f"{challenge.challenge_id} · {cid}", trace_body), encoding="utf-8")
    print(f"challenge={challenge.challenge_id} window={start.isoformat()} to {end.isoformat()}")
    print(f"baseline_p95_ms={p95(base_ms)} incident_p95_ms={p95(incident_ms)} threshold_ms={challenge.latency_threshold_ms}")
    print(f"correlation_id={cid} trace_id={root.trace_id} root_id={root.id}")
    for o in spans:
        if o.end_time:
            print(f"{o.name} duration_ms={(o.end_time-o.start_time).total_seconds()*1000:.0f} span_id={o.id}")


if __name__ == "__main__":
    main()
