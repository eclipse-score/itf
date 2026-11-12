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
"""Structured logging: every phase logs through `logging.getLogger("score.itf.core")`, so any runner
picks up a formatted, filterable trace of a session by attaching a handler to that name — no code
change, no new API to learn, whatever the runner already uses for its own logging.

Two things make this different from OCTO's diagnostics (`octo/diagnostics.py`), deliberately:
this layer *runs* things, not just resolves them, so it has a human (or a log aggregator) in front
of it the way OCTO never does — a readable `msg` is appropriate here, where OCTO's diagnostics have
none. Every field a structured/JSON formatter might want is still in
`extra={"itf_event": {...}}`, never only parseable out of the message text, so a consumer is never
forced to parse prose to get `step`, `scope`, `ok`, or `error` back out.

This is the default `observer` `Session` wires into `execute()`/`observe()` (`engine/bringup.py`)
— those functions stay logging-agnostic, taking a plain callback, same as before this existed.
"""

from __future__ import annotations

import logging

from .scopes import ROOT, display, display_json
from .labels import node_label

logger = logging.getLogger("score.itf.core")
logger.addHandler(logging.NullHandler())  # a library emits; the runner decides whether anything lands


def _emit(level: int, msg: str, kind: str, **fields) -> None:
    logger.log(level, display(msg), extra={"itf_event": {"kind": kind, **display_json(fields)}})


# ---------------------------------------------------------------- bring-up (execute/observe) events


def log_event(kind: str, data: dict) -> None:
    """The `observer(kind, data)` callback `execute()`/`observe()` already call per event."""
    step = data.get("step") or data.get("ref") or ""
    if kind == "action_started":
        _emit(logging.INFO, f"{step}: starting", kind, **data)
    elif kind == "action_finished":
        ok = data.get("ok")
        level = logging.INFO if ok else logging.ERROR
        msg = f"{step}: ok" if ok else f"{step}: failed — {data.get('error')}"
        _emit(level, msg, kind, **data)
    elif kind == "action_skipped":
        _emit(logging.INFO, f"{step}: skipped ({data.get('reason')})", kind, **data)
    elif kind == "state_probed":
        if "error" in data:
            _emit(logging.WARNING, f"{step}: probe raised {data['error']}", kind, **data)
        else:
            level = logging.DEBUG if data.get("ok") else logging.WARNING
            _emit(level, f"{step}: probe {'held' if data.get('ok') else 'did not hold'}", kind, **data)
    elif kind == "node_realized":
        _emit(logging.DEBUG, f"{data.get('ref')}: realized", kind, **data)
    else:
        _emit(logging.DEBUG, f"{kind}: {data}", kind, **data)


# ---------------------------------------------------------------- session-level phase summaries


def log_bring_up_retry(attempt: int, attempts: int, error: str, lost) -> None:
    """A bring-up attempt failed because states it had stopped holding: it plans again from what holds."""
    _emit(
        logging.WARNING,
        f"bring-up attempt {attempt}/{attempts} failed ({error}) after {', '.join(lost)} stopped holding: "
        "planning again from what holds",
        "bring_up_retried",
        attempt=attempt,
        attempts=attempts,
        lost=list(lost),
    )


def describe_packs(modules) -> list[tuple[str, str, str]]:
    """(name, version, module) of each pack module: its pack.yaml's name and version."""
    from .metadata import contributor_metadata

    described = []
    for module in modules:
        meta = contributor_metadata(module) or {}
        described.append((meta.get("name", module.__name__), str(meta.get("version", "unversioned")), module.__name__))
    return described


def log_packs(packs) -> None:
    """The packs the target file loaded: name, version (its pack.yaml) and the module they load from."""
    for name, version, module in packs:
        _emit(logging.INFO, f"pack {name} {version} ({module})", "pack_loaded", pack=name, version=version)


def log_assumptions(assumptions) -> None:
    """Log each state accepted without an action, including its declared owner and reason."""
    for assumption in assumptions:
        _emit(
            logging.INFO,
            f"assumed {assumption['state']} (owner: {assumption['owner'] or 'unspecified'}; "
            f"reason: {assumption['reason'] or 'unspecified'})",
            "state_assumed",
            **assumption,
        )


def log_nothing_to_bring_up() -> None:
    _emit(
        logging.INFO,
        "nothing to bring up: the resolved action plan has no steps",
        "bring_up_empty",
    )


def log_phase(title: str) -> None:
    """A pytest-style section banner marking the start of a session phase."""
    _emit(logging.INFO, f"{'=' * 12} itf: {title} {'=' * 12}", "phase", title=title)


def log_target_summary(target_plan) -> None:
    """One aggregate line per scope: how many roles and which contracts. Never the full role or seam
    list: `plan.json` already has that; this is for a human scanning the log, not a replacement for the
    artifact."""
    for scope in target_plan.scopes():
        nodes = [n for n in target_plan.nodes if n.scope == scope]
        tokens = target_plan.tokens(scope)
        label = display(scope) if scope == ROOT else f"target.{scope}"
        shown = [node_label(n.name, n.provider) for n in nodes] or ["(no roles)"]
        _emit(
            logging.INFO,
            f"{label}: {len(nodes)} role(s) \u2014 {', '.join(shown)}",
            "target_summary",
            scope=display(scope),
            nodes=len(nodes),
            tokens=list(tokens),
        )


def log_config_issues(issues) -> None:
    for ref, provider, message in issues:
        _emit(
            logging.ERROR,
            f"{node_label(ref, provider)}: {message}",
            "config_invalid",
            ref=ref,
            provider=provider,
            message=message,
        )


def log_resolution(gate: int, phase: str, ok: bool, diagnostics) -> None:
    if ok:
        _emit(logging.INFO, f"Gate {gate} ({phase}): resolved", "gate_resolved", gate=gate, phase=phase)
    else:
        codes = [d.code for d in diagnostics]
        _emit(
            logging.ERROR,
            f"Gate {gate} ({phase}): failed — {', '.join(codes)}",
            "gate_failed",
            gate=gate,
            phase=phase,
            codes=codes,
        )


def log_gating(decisions: dict, preflight=None) -> None:
    if preflight is not None:
        _emit(logging.INFO, preflight.render(), "compatibility_preflight", report=preflight.to_json())
    for test_id, decision in decisions.items():
        if decision.selected:
            _emit(logging.DEBUG, f"{test_id}: selected", "gating_selected", test=test_id)
        else:
            _emit(
                logging.INFO,
                f"{test_id}: deselected \u2014 {decision.reason}",
                "gating_deselected",
                test=test_id,
                reason=decision.reason,
            )


def log_plan_warnings(messages) -> None:
    for message in messages:
        _emit(logging.WARNING, f"plan warning: {message}", "plan_warning", message=message)


def log_checks(results) -> None:
    for c in results:
        if c.ok:
            _emit(logging.INFO, f"startup check {c.name}: ok", "check_ok", name=c.name)
        else:
            level = logging.ERROR if c.essential else logging.WARNING
            _emit(
                level,
                f"startup check {c.name}: failed — {c.detail}",
                "check_failed",
                name=c.name,
                detail=c.detail,
                essential=c.essential,
            )


def log_teardown(results) -> None:
    for name, ok, error in results:
        if ok:
            _emit(logging.INFO, f"teardown hook {name}: ok", "teardown_ok", name=name)
        else:
            _emit(logging.ERROR, f"teardown hook {name}: failed — {error}", "teardown_failed", name=name, error=error)


def log_drift(entry: dict) -> None:
    """A re-probe disagrees with what execution tracked: something changed a state undeclared."""
    parts = [f"{k} {', '.join(entry[k])}" for k in ("dropped", "appeared") if entry[k]]
    _emit(logging.WARNING, f"drift {entry['phase']}: {'; '.join(parts)}", "drift", **entry)


def log_unwind(report) -> None:
    if report.kept:
        _emit(logging.INFO, "unwind: kept (on_exit=keep)", "unwind_kept")
        return
    for ref in report.dismantled:
        _emit(logging.DEBUG, f"{ref}: dismantled", "unwind_dismantled", ref=ref)
    for ref, error in report.errors:
        _emit(logging.ERROR, f"{ref}: failed to dismantle — {error}", "unwind_error", ref=ref, error=error)
    _emit(
        logging.INFO,
        f"unwind: {len(report.dismantled)} dismantled, {len(report.errors)} error(s)",
        "unwind_done",
        dismantled=len(report.dismantled),
        errors=len(report.errors),
    )
