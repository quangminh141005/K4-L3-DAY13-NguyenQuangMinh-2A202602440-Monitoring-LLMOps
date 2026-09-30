"""Build a dependency-free, six-panel HTML dashboard from the JSONL log."""
from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def timestamp(row):
    try:
        return datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return None


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    return values[max(0, min(len(values) - 1, math.ceil(p * len(values) / 100) - 1))]


def fmt(value, unit=""):
    return "—" if value is None else f"{value:,.2f}{unit}"


def plot(series, limit, unit, color="#2563eb"):
    """Render one or more 60-point series and a horizontal contract limit."""
    all_values = [float(v) for points in series.values() for v in points if v is not None]
    top = max([1.0, float(limit)] + all_values) * 1.1
    def path(points):
        coords = [(40 + i * 8.8, 130 - float(v) / top * 110) for i, v in enumerate(points) if v is not None]
        return " ".join(("M" if n == 0 else "L") + f"{x:.1f},{y:.1f}" for n, (x, y) in enumerate(coords))
    threshold_y = 130 - float(limit) / top * 110
    lines = [f'<line x1="40" y1="{threshold_y:.1f}" x2="560" y2="{threshold_y:.1f}" stroke="#dc2626" stroke-dasharray="5 4"/>']
    palette = [color, "#7c3aed", "#0891b2", "#ea580c"]
    for i, (name, points) in enumerate(series.items()):
        lines.append(f'<path d="{path(points)}" fill="none" stroke="{palette[i % len(palette)]}" stroke-width="2"><title>{html.escape(name)}</title></path>')
    legend = " · ".join(f'<span style="color:{palette[i % len(palette)]}">{html.escape(name)}</span>' for i, name in enumerate(series))
    return f'<svg viewBox="0 0 580 150" role="img" aria-label="60 minute trend with threshold line">{"".join(lines)}<text x="42" y="146" font-size="11">−60m</text><text x="520" y="146" font-size="11">now</text><text x="42" y="{max(12, threshold_y-4):.1f}" fill="#dc2626" font-size="11">limit {limit:g} {html.escape(unit)}</text></svg><div class="legend">{legend}</div>'


def build(log_path, config_path, output, at_latest=False, end_at=None):
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["dashboard"]
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                row = json.loads(line)
                when = timestamp(row)
                if when:
                    records.append((when, row))
            except json.JSONDecodeError:
                continue  # A writer may have an incomplete final line.
    end = end_at or (max((t for t, _ in records), default=datetime.now(timezone.utc)) if at_latest else datetime.now(timezone.utc))
    start = end - timedelta(minutes=config["time_range_minutes"])
    rows = [(t, r) for t, r in records if start <= t <= end]
    bins = defaultdict(list)
    for t, row in rows:
        minute = min(59, int((t - start).total_seconds() // 60))
        bins[minute].append(row)
    requests = [r for _, r in rows if r.get("event") == "request_received"]
    responses = [r for _, r in rows if r.get("event") == "response_sent"]
    failures = [r for _, r in rows if r.get("event") == "request_failed"]
    panels = []
    for panel in config["panels"]:
        pid = panel["id"]
        limit = panel["threshold"]["value"]
        unit = panel["unit"]
        if pid == "latency":
            lat = [r["latency_ms"] for r in responses if isinstance(r.get("latency_ms"), (int, float))]
            ttft = [r["ttft_ms"] for r in responses if isinstance(r.get("ttft_ms"), (int, float))]
            summary = f'P50 {fmt(percentile(lat,50))} · P95 {fmt(percentile(lat,95))} · P99 {fmt(percentile(lat,99))} · TTFT P95 {fmt(percentile(ttft,95))} ms'
            series = {key: [percentile([r[field] for r in bins[i] if r.get("event") == "response_sent" and isinstance(r.get(field), (int,float))], p) for i in range(60)] for key, field, p in [("P50", "latency_ms", 50), ("P95", "latency_ms", 95), ("P99", "latency_ms", 99), ("TTFT P95", "ttft_ms", 95)]}
        elif pid == "traffic":
            summary = f'{len(requests)} requests · {len(requests)/60:.2f} requests/min'
            series = {"requests/min": [sum(r.get("event") == "request_received" for r in bins[i]) for i in range(60)]}
        elif pid == "errors":
            attempted = [r for r in responses if r.get("tool_name") == "retrieval" and isinstance(r.get("tool_success"), bool)]
            retrieval = 100 * sum(r["tool_success"] for r in attempted) / len(attempted) if attempted else None
            rate = 100 * len(failures) / len(requests) if requests else None
            breakdown = ", ".join(f"{html.escape(str(k))}: {v}" for k, v in Counter(r.get("error_type") or "unknown" for r in failures).items()) or "none"
            summary = f'Error rate {fmt(rate, "%")} · retrieval success {fmt(retrieval, "%")} · errors: {breakdown}'
            series = {"error rate %": [100 * sum(r.get("event") == "request_failed" for r in bins[i]) / n if (n := sum(r.get("event") == "request_received" for r in bins[i])) else None for i in range(60)]}
        elif pid == "cost":
            total = sum(float(r.get("cost_usd") or 0) for r in responses)
            summary = f'Window total ${total:.4f}'
            series = {"cumulative USD": [sum(float(r.get("cost_usd") or 0) for j in range(i + 1) for r in bins[j] if r.get("event") == "response_sent") for i in range(60)]}
        elif pid == "tokens":
            tin = sum(int(r.get("tokens_in") or 0) for r in responses)
            tout = sum(int(r.get("tokens_out") or 0) for r in responses)
            summary = f'Input {tin:,} · output {tout:,} tokens'
            series = {key: [sum(int(r.get(field) or 0) for j in range(i + 1) for r in bins[j] if r.get("event") == "response_sent") for i in range(60)] for key, field in [("cumulative input", "tokens_in"), ("cumulative output", "tokens_out")]}
        else:
            scores = [r["quality_score"] for r in responses if isinstance(r.get("quality_score"), (int, float))]
            summary = f'Mean {fmt(sum(scores)/len(scores) if scores else None)} / 1'
            series = {"mean quality": [sum(v)/len(v) if (v := [r["quality_score"] for r in bins[i] if r.get("event") == "response_sent" and isinstance(r.get("quality_score"), (int,float))]) else None for i in range(60)]}
        direction = "≤" if panel["threshold"]["operator"] == "lte" else "≥"
        panels.append(f'<section><h2>{html.escape(panel["title"])}</h2><p class="meta">{html.escape(unit)} · 60 min · {html.escape(panel["threshold"]["aggregation"])} {direction} {limit}</p><p>{summary}</p>{plot(series, limit, unit)}</section>')
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{html.escape(config["title"])}</title><style>body{{font:15px system-ui;background:#f4f7fb;color:#14213d;margin:2rem}}header{{margin-bottom:1.5rem}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:1rem}}section{{background:white;border:1px solid #dce3ec;border-radius:12px;padding:1.2rem;min-width:0}}h2{{margin:.1rem 0}}.meta,.legend,small{{color:#52637a}}svg{{width:100%;height:auto}}.legend{{font-size:12px}}@media(max-width:500px){{body{{margin:1rem}}.grid{{grid-template-columns:1fr}}}}</style><header><h1>{html.escape(config["title"])}</h1><p>Source: {html.escape(str(log_path))} · 60 minutes: {start.isoformat()} to {end.isoformat()} · {len(rows)} log events</p><small>Red dashed lines show contract thresholds. Empty series mean no samples; zero is shown only when measured.</small></header><main class="grid">{"".join(panels)}</main></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(f"Wrote {output} with {len(panels)} panels and {len(rows)} events")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, default=ROOT / "data/logs.jsonl")
    parser.add_argument("--config", type=Path, default=ROOT / "config/dashboard.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "submission/evidence/dashboard.html")
    parser.add_argument("--at-latest", action="store_true", help="Use the latest log timestamp for historical evidence")
    parser.add_argument("--end", help="UTC end timestamp for a historical 60-minute window, ISO 8601")
    args = parser.parse_args()
    end_at = datetime.fromisoformat(args.end.replace("Z", "+00:00")) if args.end else None
    if end_at and end_at.utcoffset() is None:
        parser.error("--end requires a timezone, for example 2026-09-29T17:00:00Z")
    build(args.logs, args.config, args.output, args.at_latest, end_at)
