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
"""Persist partial results even after a failed gate or interrupted bring-up.

JSON remains the source of facts; the HTML report projects the same resolved plans for readers.
"""

from __future__ import annotations

import json
from pathlib import Path

from .engine.render import render
from .engine.report import render_target_html
from .engine.config import plan_secrets, redact_target, shown_config
from .engine.labels import label_steps, node_label
from .engine.scopes import display, display_json
from .engine.secrets import mask
from .octo import GoalClaim, claims_to_json
from .target_handle import target_view


def _write_json(path: Path, data) -> None:
    path.write_text(mask(json.dumps(data, indent=2, sort_keys=True, default=str)), encoding="utf-8")


def _goal_refs(init_claims) -> tuple[str, ...]:
    return tuple(sorted(f"{c.scope}:{t}" for c in init_claims if isinstance(c, GoalClaim) for t in c.states))


def _changed(cache: dict | None, name: str, *sources) -> bool:
    """True unless `name` was last written from these very objects; session state is replaced,
    never mutated, so identity says whether a file's content can have changed."""
    if cache is None:
        return True
    prev = cache.get(name)
    if prev is not None and len(prev) == len(sources) and all(a is b for a, b in zip(prev, sources)):
        return False
    cache[name] = sources
    return True


def write_artifacts(run_dir: Path, session, *, cache: dict | None = None, level: str = "full") -> None:
    """Write the artifacts of `level`; with `cache`, skip the ones whose inputs are unchanged since the last call.

    `none` writes nothing. `standard` writes what a person reads: the plan report once the target was brought up
    or planning failed, and the diagnostics when there are any. `full` writes every file, the machine-readable
    ones (plan, claims, gating, run, unwind) included."""
    if level == "none":
        return
    failed = getattr(session, "_resolution_failure", None) is not None or bool(getattr(session, "_config_issues", ()))
    ran = getattr(session, "_brought_up", False)
    if level == "standard" and not (failed or ran):
        return
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    catalog = getattr(session, "_catalog", None)
    schemas = getattr(catalog, "config_schemas", {})
    original_target = getattr(session, "_target_plan", None)
    target_plan = redact_target(original_target, schemas)
    _write_target_html(run_dir, session, cache, catalog, schemas, original_target, target_plan)
    _write_diagnostics(run_dir, session, cache, catalog, always=level == "full")
    if level != "full":
        return
    _write_claims_json(run_dir, session, cache, catalog, schemas, original_target)
    _write_plan_json(run_dir, session, cache, catalog, schemas, original_target, target_plan)
    _write_gating(run_dir, session, cache)
    _write_run(run_dir, session, cache)
    _write_unwind(run_dir, session, cache)


def _write_claims_json(run_dir, session, cache, catalog, schemas, original_target) -> None:
    setup_claims = getattr(session, "_setup_claims", None) or ()
    init_claims = getattr(session, "_init_claims", None) or ()
    if not _changed(cache, "claims.json", setup_claims, init_claims, original_target, catalog):
        return
    selected = {node.ref: node.provider for node in original_target.nodes} if original_target else {}
    secrets = plan_secrets(original_target, schemas)

    def safe_config(provider, config):
        return shown_config(config, schemas.get(provider), secrets)

    _write_claims(run_dir, setup_claims, init_claims, safe_config, selected)


def plan_document(session) -> dict:
    """The plan as data, secrets redacted: what `plan.json`, `itf plan --json` and the Bazel compile step hold."""
    catalog = getattr(session, "_catalog", None)
    schemas = getattr(catalog, "config_schemas", {})
    return _plan_document(session, catalog, schemas, redact_target(getattr(session, "_target_plan", None), schemas))


def _write_plan_json(run_dir, session, cache, catalog, schemas, original_target, target_plan) -> None:
    action_plan = getattr(session, "_action_plan", None)
    assumed = getattr(session, "_assumed", None) or ()
    handle = getattr(session, "_target", None)
    config_issues = getattr(session, "_config_issues", ())
    if not _changed(cache, "plan.json", original_target, action_plan, assumed, handle, catalog, config_issues):
        return
    _write_json(run_dir / "plan.json", _plan_document(session, catalog, schemas, target_plan))


def _plan_document(session, catalog, schemas, target_plan) -> dict:
    action_plan = getattr(session, "_action_plan", None)
    assumed = getattr(session, "_assumed", None) or ()
    handle = getattr(session, "_target", None)
    config_issues = getattr(session, "_config_issues", ())
    target = target_view(target_plan, handle.scopes() if handle else ()) if target_plan is not None else None
    action = display_json(label_steps(action_plan.to_json(), catalog)) if action_plan is not None else None
    return {
        "target": target,
        "action": action,
        "assumptions": display_json(list(assumed)),
        "config_schemas": {name: schema.describe() for name, schema in sorted(schemas.items())},
        "config_issues": [
            dict(ref=display(ref), provider=provider, message=message) for ref, provider, message in config_issues
        ],
    }


def _write_target_html(run_dir, session, cache, catalog, schemas, original_target, target_plan) -> None:
    action_plan = getattr(session, "_action_plan", None)
    config_issues = getattr(session, "_config_issues", ())
    run_report = getattr(session, "_run_report", None)
    failure = getattr(session, "_resolution_failure", None)
    retries = getattr(session, "_retries", ())
    if target_plan is None:
        return
    sources = (original_target, action_plan, run_report, catalog, config_issues, failure, retries)
    if not _changed(cache, "target.html", *sources):
        return
    page = render_target_html(
        target_plan,
        action_plan,
        title=f"itf target · {run_dir.name}",
        run_report=run_report,
        config_schemas={name: schema.describe() for name, schema in schemas.items()},
        config_issues=config_issues,
        failure=failure,
        goals=_goal_refs(getattr(session, "_init_claims", None) or ()),
        retries=retries,
    )
    (run_dir / "target.html").write_text(mask(page), encoding="utf-8")


def _write_diagnostics(run_dir, session, cache, catalog, *, always: bool = True) -> None:
    failure = getattr(session, "_resolution_failure", None)
    config_issues = getattr(session, "_config_issues", ())
    if not _changed(cache, "diagnostics.txt", failure, config_issues):
        return
    text = ""
    if failure is not None:
        roles = session._compiled.roles if getattr(session, "_compiled", None) is not None else {}
        text = render(failure.diagnostics, gate=failure.gate, phase=failure.phase, catalog=catalog, roles=roles)
    text += "\n".join(f"{node_label(display(ref), provider)}: {message}" for ref, provider, message in config_issues)
    if text or always:
        (run_dir / "diagnostics.txt").write_text(mask(text), encoding="utf-8")


def _write_gating(run_dir, session, cache) -> None:
    decisions = getattr(session, "_gating_decisions", None) or ()
    if _changed(cache, "gating.json", decisions):
        _write_json(
            run_dir / "gating.json",
            [{"test": name, "selected": dec.selected, "reason": dec.reason} for name, dec in decisions],
        )
    preflight = getattr(session, "_preflight_report", None)
    if preflight is not None and _changed(cache, "preflight.json", preflight):
        _write_json(run_dir / "preflight.json", preflight.to_json())


def _write_run(run_dir, session, cache) -> None:
    run_report = getattr(session, "_run_report", None)
    check_results = getattr(session, "_check_results", None) or ()
    pre_observation = getattr(session, "_pre_observation", None)
    probe_stats = getattr(session, "_probe_stats", None)
    drift = getattr(session, "_drift", None)
    retries = getattr(session, "_retries", ())
    if not _changed(cache, "run.json", run_report, check_results, pre_observation, probe_stats, drift, retries):
        return
    _write_json(
        run_dir / "run.json",
        display_json(
            {
                "probed_before_gate2": sorted(pre_observation.holds) if pre_observation else [],
                "executed": list(run_report.executed) if run_report else [],
                "skipped": list(run_report.skipped) if run_report else [],
                "retries": list(retries),
                "checks": [
                    {"name": c.name, "ok": c.ok, "detail": c.detail, "essential": c.essential} for c in check_results
                ],
                "probes": probe_stats or {},
                "drift": list(drift or ()),
            }
        ),
    )


def _write_unwind(run_dir, session, cache) -> None:
    report = getattr(session, "_unwind_report", None)
    teardown_results = getattr(session, "_teardown_results", None) or ()
    if not _changed(cache, "unwind.json", report, teardown_results):
        return
    _write_json(
        run_dir / "unwind.json",
        display_json(
            {
                "teardown_hooks": [{"name": n, "ok": ok, "error": err} for n, ok, err in teardown_results],
                "kept": report.kept if report else None,
                "probed": list(report.probed) if report else [],
                "dismantled": list(report.dismantled) if report else [],
                "errors": [{"ref": r, "error": e} for r, e in report.errors] if report else [],
            }
        ),
    )


def _write_claims(run_dir: Path, setup_claims, init_claims, safe_config, selected) -> None:
    setup_json = claims_to_json(setup_claims)
    for entry in setup_json:
        if entry.get("_kind") == "NodeClaim":
            ref = f"{entry['scope']}.{entry['name']}"
            entry["config"] = safe_config(entry.get("using") or selected.get(ref), entry["config"])
    _write_json(
        run_dir / "claims.json",
        {
            "setup": setup_json,
            "init": claims_to_json(init_claims),
        },
    )
