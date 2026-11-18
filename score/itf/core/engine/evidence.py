# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************
"""Run evidence: one structured record of what a run did, and a static page that shows it.

`build_record` only reads what the session already knows; nothing is probed or run, so it is safe to
call at close, also after a failed bring-up. The record (`evidence.json`) is the source of truth, the
page (`evidence.html`) is a projection that can be regenerated from it (`render_html`), and
`summarize` aggregates several records.
"""

from __future__ import annotations

import datetime
import html
import json
from pathlib import Path

from .scopes import display_json
from .secrets import mask

SCHEMA = 1
JSON_NAME = "evidence.json"
HTML_NAME = "evidence.html"


# ---------------------------------------------------------------- the record


def _plan_summary(session) -> dict:
    plan = getattr(session, "_target_plan", None)
    nodes = []
    if plan is not None:
        nodes = [{"ref": n.ref, "provider": n.provider, "contract": getattr(n, "contract", None)} for n in plan.nodes]
    action = getattr(session, "_action_plan", None)
    full = getattr(session, "_full_plan", None)
    return {
        "nodes": nodes,
        "scopes": sorted(plan.scopes()) if plan is not None else [],
        "planned_steps": [
            {"key": s.key, "impl": s.impl, "delivers": list(s.delivers), "requires": list(s.requires)}
            for s in (action.steps if action is not None else ())
        ],
        "full_plan_steps": len(full.steps) if full is not None else 0,
    }


def _steps(session) -> list:
    """Every step that ran, was skipped or failed (in order, with its duration), then planned steps that
    never got that far.
    A step that failed in a bring-up attempt that was retried is "failed, retried": the run recovered from it.
    Each row carries the bring-up attempt it ran in, or None outside bring-up."""
    events = getattr(session, "_events", ())
    retried = {r["attempt"] for r in getattr(session, "_retries", ())}
    out: list = []
    started: dict = {}
    seen: set = set()
    for e in events:
        kind, step, attempt = e["kind"], e.get("step"), e.get("attempt")
        if kind == "action_started":
            started[step] = e["t"]
        elif kind == "action_finished":
            outcome = "ok" if e.get("ok") else ("failed, retried" if attempt in retried else "failed")
            out.append(
                {
                    "step": step,
                    "phase": e["phase"],
                    "attempt": attempt,
                    "outcome": outcome,
                    "ms": round((e["t"] - started.pop(step, e["t"])) * 1e3, 3),
                    "error": e.get("error", ""),
                }
            )
            seen.add(step)
        elif kind == "action_skipped":
            out.append(
                {
                    "step": step,
                    "phase": e["phase"],
                    "attempt": attempt,
                    "outcome": "skipped",
                    "ms": 0.0,
                    "error": e.get("reason", ""),
                }
            )
            seen.add(step)
    action = getattr(session, "_action_plan", None)
    for s in action.steps if action is not None else ():
        if s.key not in seen:
            out.append({"step": s.key, "phase": "", "attempt": None, "outcome": "not run", "ms": 0.0, "error": ""})
    return out


def _probes(session) -> list:
    return [
        {
            "phase": e["phase"],
            "step": e.get("step", ""),
            "states": list(e.get("states", ())),
            "ok": e.get("ok"),
            "ms": round(e.get("ms", 0.0), 3),
            "error": e.get("error", ""),
        }
        for e in getattr(session, "_events", ())
        if e["kind"] == "state_probed"
    ]


def _checks(session) -> list:
    return [
        {"name": c.name, "ok": c.ok, "detail": c.detail, "essential": c.essential}
        for c in getattr(session, "_check_results", ())
    ]


def _unwind(session) -> dict:
    unwind = getattr(session, "_unwind_report", None)
    if unwind is None:
        return {"kept": None, "dismantled": [], "errors": []}
    return {
        "kept": unwind.kept,
        "dismantled": list(unwind.dismantled),
        "errors": [{"ref": r, "error": e} for r, e in unwind.errors],
    }


def _failure_text(session) -> str:
    failure = getattr(session, "_resolution_failure", None)
    return getattr(session, "_failure_text", "") or (failure.rendered if failure is not None else "")


def build_record(session) -> dict:
    failure_text = _failure_text(session)
    checks = _checks(session)
    steps = _steps(session)
    ok = (
        not failure_text
        and not any(s["outcome"] == "failed" for s in steps)
        and not any(not c["ok"] and c["essential"] for c in checks)
    )
    record = {
        "schema": SCHEMA,
        "run": Path(session.run_dir).name,
        "written": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "outcome": "ok" if ok else "failed",
        "ready": bool(getattr(session, "_ready", False)),
        "plan": _plan_summary(session),
        "steps": steps,
        "retries": list(getattr(session, "_retries", ())),
        "probes": _probes(session),
        "probe_totals": getattr(session, "_probe_stats", {}),
        "drift": list(getattr(session, "_drift", ())),
        "checks": checks,
        "teardown": [{"name": n, "ok": ok, "error": err} for n, ok, err in getattr(session, "_teardown_results", ())],
        "unwind": _unwind(session),
        "leaked_processes": list(getattr(session, "_leaked_processes", ())),
        "failure": failure_text,
    }
    return display_json(record)


def write_evidence(run_dir, session) -> Path:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    record = build_record(session)
    (run_dir / JSON_NAME).write_text(mask(json.dumps(record, indent=2, default=str)), encoding="utf-8")
    return write_html(run_dir, record)


def write_html(run_dir, record=None, output=None) -> Path:
    """(Re)generate the page from `evidence.json` in `run_dir` (or from `record`), into the run directory or
    `output`."""
    run_dir = Path(run_dir)
    if record is None:
        record = load_record(run_dir)
    path = Path(output) if output is not None else run_dir / HTML_NAME
    path.write_text(mask(render_html(record)), encoding="utf-8")
    return path


def load_record(run_dir) -> dict:
    path = Path(run_dir) / JSON_NAME
    if not path.is_file():
        raise FileNotFoundError(f"{path}: no evidence record (was the session closed?)")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the page

_CSS = """
:root{--bg:#fff;--fg:#1b1f24;--muted:#5b6570;--line:#d8dee4;--panel:#f6f8fa;--ok:#1a7f37;--bad:#cf222e;--warn:#9a6700;--bar:#0969da}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--panel:#161b22;--ok:#3fb950;--bad:#f85149;--warn:#d29922;--bar:#58a6ff}}
body{margin:0 auto;max-width:72rem;padding:1rem 16px 3rem;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
h1{font-size:1.4rem;margin:.5rem 0}h2{font-size:1.1rem;margin:2rem 0 .5rem;border-bottom:1px solid var(--line);padding-bottom:.25rem}
table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}th,td{text-align:left;padding:.3rem .6rem;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}code,pre{font:13px ui-monospace,monospace}pre{background:var(--panel);padding:.75rem;overflow-x:auto;border-radius:6px}
.badge{display:inline-block;padding:0 .6rem;border-radius:1rem;color:#fff;font-weight:600}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.badge.ok{background:var(--ok);color:#fff}.badge.bad{background:var(--bad);color:#fff}.muted{color:var(--muted)}
.bar{display:inline-block;height:.6rem;background:var(--bar);border-radius:3px;vertical-align:middle}
"""


def _e(value) -> str:
    return html.escape(str(value))


def _cls(ok) -> str:
    return "ok" if ok else "bad"


def _table(headers, rows) -> str:
    if not rows:
        return '<p class="muted">none</p>'
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def _nodes_table(plan: dict) -> str:
    return _table(
        ["role", "factory", "contract"],
        [
            [f"<code>{_e(n['ref'])}</code>", _e(n["provider"]), f"<code>{_e(n['contract'] or '')}</code>"]
            for n in plan.get("nodes", [])
        ],
    )


_STEP_CLASS = {"ok": "ok", "failed": "bad", "failed, retried": "muted", "skipped": "muted", "not run": "muted"}


def _step_row(s: dict, longest: float) -> list:
    width = max(int(s["ms"] / longest * 200), 1) if s["ms"] else 0
    return [
        f"<code>{_e(s['step'])}</code>",
        f'<span class="{_STEP_CLASS.get(s["outcome"], "")}">{_e(s["outcome"])}</span>',
        _e(s["phase"]),
        _e(s.get("attempt") or ""),
        f'{s["ms"]:.1f} ms <span class="bar" style="width:{width}px"></span>',
        _e(s["error"]),
    ]


def _probe_row(p: dict) -> list:
    state = "error" if p["ok"] is None else ("held" if p["ok"] else "did not hold")
    return [
        f"<code>{_e(p['step'])}</code>",
        _e(", ".join(p["states"])),
        f'<span class="{_cls(p["ok"])}">{state}</span>',
        _e(p["phase"]),
        f"{p['ms']:.1f} ms",
        _e(p["error"]),
    ]


def _verdict(ok) -> str:
    return f'<span class="{_cls(ok)}">{"ok" if ok else "failed"}</span>'


def _checks_table(record: dict) -> str:
    return _table(
        ["check", "result", "essential", "detail"],
        [
            [_e(c["name"]), _verdict(c["ok"]), "yes" if c["essential"] else "no", _e(c["detail"])]
            for c in record.get("checks", [])
        ],
    )


def _teardown_table(record: dict) -> str:
    return _table(
        ["teardown hook", "result", "error"],
        [[_e(t["name"]), _verdict(t["ok"]), _e(t["error"])] for t in record.get("teardown", [])],
    )


def _unwind_html(unwind: dict) -> str:
    return (
        f"<p>dismantled: {_e(', '.join(unwind.get('dismantled', [])) or '-')}"
        + (" (kept: not unwound)" if unwind.get("kept") else "")
        + "</p>"
        + "".join(f'<p class="bad">{_e(e["ref"])}: {_e(e["error"])}</p>' for e in unwind.get("errors", []))
    )


def _retries_html(retries: list) -> str:
    return "".join(
        f'<p class="muted">attempt {r["attempt"]} failed ({_e(r["error"])}) after {_e(", ".join(r["lost"]))} '
        "stopped holding: bring-up planned again from what held</p>"
        for r in retries
    )


def _leaked_html(leaked: list) -> str:
    if leaked:
        return '<p class="bad">' + _e(", ".join(leaked)) + "</p>"
    return '<p class="ok">none: no process outlived the run</p>'


def render_html(record: dict) -> str:
    steps = record.get("steps", [])
    longest = max([s["ms"] for s in steps] + [1.0])
    outcome = record.get("outcome", "failed")
    failure = record.get("failure")
    failure_html = f"<h2>Failure</h2><pre>{_e(failure)}</pre>" if failure else ""
    step_table = _table(
        ["step", "outcome", "phase", "attempt", "time", "detail"], [_step_row(s, longest) for s in steps]
    )
    probe_table = _table(
        ["step", "states", "result", "phase", "time", "error"], [_probe_row(p) for p in record.get("probes", [])]
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>itf evidence {_e(record.get('run', ''))}</title><style>{_CSS}</style></head><body>"
        f'<h1>itf evidence <code>{_e(record.get("run", ""))}</code> <span class="badge {_cls(outcome == "ok")}">{_e(outcome)}</span></h1>'
        f'<p class="muted">written {_e(record.get("written", ""))} &middot; ready: {"yes" if record.get("ready") else "no"}</p>'
        f"{failure_html}"
        f"<h2>Target</h2>{_nodes_table(record.get('plan', {}))}"
        f"<h2>Steps</h2>{_retries_html(record.get('retries', []))}{step_table}"
        f"<h2>Probes</h2>{probe_table}"
        f"<h2>Startup checks</h2>{_checks_table(record)}"
        f"<h2>Teardown</h2>{_teardown_table(record)}{_unwind_html(record.get('unwind', {}))}"
        f"<h2>Leaked processes</h2>{_leaked_html(record.get('leaked_processes', []))}"
        "</body></html>"
    )


# ---------------------------------------------------------------- aggregate across runs


def summarize(run_dirs, top: int = 10) -> dict:
    """Slowest probes, probes that were false at least once, failing steps, across runs."""
    slowest: dict = {}
    flaky: dict = {}
    failing: dict = {}
    runs = failed_runs = 0
    for run_dir in run_dirs:
        record = load_record(run_dir)
        runs += 1
        failed_runs += record.get("outcome") != "ok"
        for p in record.get("probes", []):
            key = p["step"]
            s = slowest.setdefault(key, {"step": key, "max_ms": 0.0, "total_ms": 0.0, "count": 0})
            s["max_ms"] = max(s["max_ms"], p["ms"])
            s["total_ms"] += p["ms"]
            s["count"] += 1
            if p["ok"] is not True:
                f = flaky.setdefault(key, {"step": key, "false": 0, "count": 0})
                f["false"] += 1
        for p in record.get("probes", []):
            if p["step"] in flaky:
                flaky[p["step"]]["count"] += 1
        for s in record.get("steps", []):
            if s["outcome"] == "failed":
                f = failing.setdefault(s["step"], {"step": s["step"], "failures": 0, "last_error": ""})
                f["failures"] += 1
                f["last_error"] = s["error"]
    ranked = sorted(slowest.values(), key=lambda s: -s["max_ms"])[:top]
    return {
        "runs": runs,
        "failed_runs": failed_runs,
        "slowest_probes": [dict(s, mean_ms=round(s["total_ms"] / s["count"], 3)) for s in ranked],
        "probes_false_at_least_once": sorted(flaky.values(), key=lambda f: -f["false"]),
        "failing_steps": sorted(failing.values(), key=lambda f: -f["failures"]),
    }


def render_summary(summary: dict) -> str:
    lines = [f"{summary['runs']} run(s), {summary['failed_runs']} failed", "", "Slowest probes (max ms)"]
    lines += [
        f"  {s['max_ms']:9.1f}  mean {s['mean_ms']:8.1f}  x{s['count']:<3} {s['step']}"
        for s in summary["slowest_probes"]
    ] or ["  -"]
    lines += ["", "Probes that were false at least once"]
    lines += [f"  {f['false']}/{f['count']}  {f['step']}" for f in summary["probes_false_at_least_once"]] or ["  -"]
    lines += ["", "Failing steps"]
    lines += [f"  {f['failures']}x  {f['step']}  {f['last_error']}" for f in summary["failing_steps"]] or ["  -"]
    return "\n".join(lines)
