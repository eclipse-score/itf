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
"""The session: one catalog, one target file, one resolution, one bring-up.

`Session` is the entry point and keeps the run's phase; the work is done by its parts:

| Part | Module | Does |
|---|---|---|
| `Resolution` | `resolution.py` | target file to plans: packs, catalog, gate 1, the checks between the gates, gate 2 |
| `TargetStates` | `states.py` | what holds at run time: observe, plan the delta, run it (bring-up, reach, discard) |
| `RunRecord` | `record.py` | what the run did, for the log, the run artifacts and the evidence |

Artifacts are written after every phase, even a failed one, so a partially resolved run remains inspectable.
"""

from __future__ import annotations

import contextlib
import dataclasses
from pathlib import Path

from .. import gating
from ..engine.close import SessionView, UnwindReport, run_startup_checks, run_teardown_hooks, unwind
from ..engine.failure import Failure, checks_failure, teardown_failure
from ..engine.labels import label_steps
from ..engine.log import log_checks, log_gating, log_phase, log_teardown, log_unwind
from ..engine.realize import Realization
from ..engine.scopes import display_json
from ..engine.secrets import Secrets
from ..frontends.target_source import TargetSource, locate
from ..process import ProcessWrapper
from ..target_handle import Target, target_view
from .errors import ConfigValidationFailed, NotReady, ResolutionFailed, TargetNameClash
from .options import ARTIFACTS, GATING, ON_EXIT, REUSE, UNSET, attempts, one_of
from .record import RunRecord
from .resolution import PRECEDENCE, Resolution, follow_roots, log_target_file
from .states import TargetStates

__all__ = [
    "ARTIFACTS",
    "ConfigValidationFailed",
    "DescribeResult",
    "GATING",
    "NotReady",
    "ON_EXIT",
    "PRECEDENCE",
    "REUSE",
    "Resolution",
    "ResolutionFailed",
    "RunRecord",
    "Session",
    "TargetNameClash",
    "TargetStates",
    "compose",
    "describe",
    "log_target_file",
]

# The project's policy roots, followed as pytest follows `pytest_plugins` (the contract tools read them too).
_roots = follow_roots


class Session:
    """One run. `target` (a path, inline YAML/JSON text or a `TargetSource`) is the target file;
    `overrides` are further target files merged over it by role. Packs load from the factory labels the
    target file names; project capabilities and actions come from `roots` (the project's policy, their
    `pytest_plugins` followed) or `contributors`, the (module, origin) pairs a runner already loaded. Without a
    target file it is empty, which is valid. `gating` is `skip` (deselect) or `fail`, `reuse` is `probe` (keep what
    holds) or `fresh`, `on_exit` is `unwind` or `keep`. `definitions` (contract name -> `gating.Definition`, see
    `score.itf.core.adapters.definitions`) is optional: with it a plan warns about deprecated contracts; nothing
    needs it.

    Read it through `target` (the roles), `target_plan`, `action_plan`, `catalog` and `observed`; `resolution`,
    `states` and `record` are its parts."""

    def __init__(
        self,
        roots=(),
        *,
        contributors=None,
        target=None,
        overrides=(),
        plan_only: bool = False,
        gating: str = "skip",
        reuse: str = "probe",
        on_exit: str = "unwind",
        definitions=None,
        run_dir=None,
        artifacts: str = "standard",
        unset: str = "fail",
        bring_up_attempts: int = 1,
    ):
        self.roots = [roots] if isinstance(roots, str) else list(roots)
        self.contributors = contributors
        self.target_source: TargetSource | None = locate(target, "target=") if target is not None else None
        if isinstance(overrides, (str, TargetSource)):
            overrides = [overrides]
        self.override_sources = tuple(locate(o, "overrides=") for o in overrides)
        if self.override_sources and self.target_source is None:
            raise ValueError("overrides need a target file: Session(target=..., overrides=[...])")
        self.plan_only = plan_only
        self.gating = one_of("gating", gating, GATING)
        self.reuse = one_of("reuse", reuse, REUSE)
        self.on_exit = one_of("on_exit", on_exit, ON_EXIT)
        self.artifacts = one_of("artifacts", artifacts, ARTIFACTS)
        self.unset = one_of("unset", unset, UNSET)
        self.bring_up_attempts = attempts(bring_up_attempts)
        if self.unset == "placeholder" and not plan_only:
            raise ValueError("unset='placeholder' is for plan_only sessions: nothing may be built from a placeholder")
        self.definitions = dict(definitions) if definitions else {}
        self.run_dir = Path(run_dir) if run_dir is not None else Path("itf-run")

        self.secrets = Secrets()  # the values of sensitive settings: masked wherever ITF shows text
        self.record = RunRecord(self.secrets)
        self.resolution: Resolution | None = None
        self.states: TargetStates | None = None
        self.handle: Target | None = None  # `target`, or None before gate 1 succeeded
        self.phase = "new"
        self._process_owner_token = None
        self._artifact_cache: dict = {}

    def _require_phase(self, operation: str, allowed: tuple[str, ...]) -> None:
        if self.phase not in allowed:
            expected = " or ".join(allowed)
            raise RuntimeError(f"cannot {operation} a session in phase {self.phase!r}; expected {expected}")

    # ---- phases ----

    def resolve(self) -> "Session":
        """Both gates, without probing or building anything (see `resolution.py`)."""
        self._require_phase("resolve", ("new",))
        self.phase = "resolving"
        log_phase("resolve")
        self._process_owner_token = ProcessWrapper.activate(self)  # host processes started here belong to this run
        resolution = self.resolution = Resolution(self.record)
        try:
            resolution.load(self.target_source, self.override_sources)
            resolution.declare_parts(self.contributors, self.roots)
            resolution.plan_roles(placeholders=self.unset == "placeholder", definitions=self.definitions)
            realization = Realization(resolution.target_plan, owner=self)
            self.handle = Target(self, resolution.scopes)
            resolution.plan_actions()
            self.states = TargetStates(resolution, realization, self.record, reuse=self.reuse)
            if self.plan_only:
                self._dry_run_check()
        except BaseException:
            self.phase = "failed"
            raise
        else:
            self.phase = "resolved"
        finally:
            self._write_artifacts()
        return self

    def _dry_run_check(self) -> None:
        """A dry run resolves every `impl`, teardown and probe reference; constructs nothing."""
        steps = self.states.action_plan.steps
        extra = tuple(s.impl for s in steps) + tuple(probe for s in steps for _, probe in s.state_probes())
        self.states.realization.resolve_all(extra_impls=extra)

    def select(self, requirements: dict) -> dict:
        """`requirements`: test id -> tuple[Requirement, ...]. Returns test id -> GatingDecision.
        A requirement without `scope` is checked against the root scope only. Every requirement is
        evaluated; `preflight_report` retains grouped profiles and diagnostics even for deselected tests."""
        self._require_phase("select tests for", ("resolved",))
        report = gating.preflight(requirements, self.resolution.target_plan, self.resolution.factory_majors)
        self.record.preflight_report = report
        self.record.gating_decisions = tuple(report.decisions.items())
        log_gating(report.decisions, report)
        self._write_artifacts()
        return report.decisions

    def probe(self, states: frozenset | None = None) -> frozenset:
        """Run the probes of the full plan (of `states` only, qualified `scope:state`, when given) and return what
        holds. `itf down` uses it to see what a fresh session finds; nothing is built that no probe needs."""
        self._require_phase("probe", ("resolved", "up"))
        return self.states.probe(states)

    def bring_up(self) -> None:
        """Run what the goals need (see `TargetStates.bring_up`), then the startup checks (`itf_verify`). The checks
        run only once the states hold, so a failing check means an unhealthy target, not one still being built;
        a failing essential check stops the session before any test runs."""
        self._require_phase("bring up", ("resolved",))
        if self.plan_only:
            raise RuntimeError("a plan_only session does not bring up")
        self.phase = "bringing_up"
        try:
            self.record.brought_up = True
            self.states.bring_up(self.bring_up_attempts, evidence_dir=self.evidence_dir, written=self._write_artifacts)
            self._run_startup_checks()
        except BaseException:
            self.phase = "failed"
            raise
        self.phase = "up"

    def _run_startup_checks(self) -> None:
        record = self.record
        log_phase("startup checks")
        record.check_results = run_startup_checks(self.resolution.registry, SessionView(self))
        log_checks(
            tuple(dataclasses.replace(check, detail=self.secrets.mask(check.detail)) for check in record.check_results)
        )
        self._write_artifacts()
        failing = [c for c in record.check_results if c.essential and not c.ok]
        if failing:
            failure = record.safe_failure(checks_failure(record.check_results, self.evidence_dir))
            record.failure_text = failure.render()
            raise NotReady(
                f"{len(failing)} essential startup check(s) failed: {', '.join(c.name for c in failing)}", failure
            )
        record.ready = True

    def reach(self, *states: str, assume: tuple[str, ...] = (), reason: str = "", owner: str = ""):
        """Re-plan and execute the delta to reach `states`: `token` or `:token` is the root scope,
        `dev1:token` a device. `assume` (same form) bypasses a dependency's producer for this call
        only, without evidence that it holds; the plan records which ids were taken on faith and,
        via `owner`/`reason`, who said so.
        """
        self._require_phase("reach states in", ("resolved", "bringing_up", "up"))
        try:
            return self.states.reach(states, scopes=self.target.scopes(), assume=assume, reason=reason, owner=owner)
        finally:
            self._write_artifacts()

    def renew(self, *nodes: str):
        """Rebuild nodes from scratch, then reach every goal so far again: `name` or `.name` is a
        root node, `dev1.name` a device's. Each node and every realized node bound to it is
        dismantled; a state delivered through one of them, or requiring such a state, is not
        taken as holding even if its probe says so, so its producer runs again.
        """
        self._require_phase("renew nodes in", ("resolved", "up"))
        # Renewal is a primitive, not a mode: the caller decides when (a fixture, a test). Nothing in ITF renews
        # on its own, so ITF never fights pytest's own fixture scoping.
        log_phase(f"renew {', '.join(nodes)}")
        self.discard(*nodes)
        try:
            return self.states.reach((), scopes=self.target.scopes())
        finally:
            self._write_artifacts()

    def discard(self, *roles: str) -> None:
        """Dismantle roles (and every built role bound to them) without reaching anything: the next access
        builds them afresh, so a caller may adjust a new object before `reach`. The states whose evidence ran
        through a dismantled role are forgotten until the next `reach` delivers them again."""
        self._require_phase("discard roles in", ("resolved", "up"))
        self.states.discard(roles)

    def close(self) -> None:
        """Teardown hooks first, while the target still runs (they collect evidence from it), then unwind
        dismantles what was built; then leaked processes are reaped and the run files written. Idempotent, so an
        error path and the normal path may both call it; closing never raises for what it finds (see
        `close_problems`)."""
        if self.phase in ("closing", "closed"):
            return
        self.phase = "closing"
        record = self.record
        try:
            log_phase("close")
            if record.brought_up and self.resolution is not None and self.resolution.registry is not None:
                record.teardown_results = run_teardown_hooks(self.resolution.registry, SessionView(self))
                log_teardown(tuple((name, ok, self.secrets.mask(error)) for name, ok, error in record.teardown_results))
            if self.states is not None:
                meter = record.meter()
                record.unwind_report = unwind(
                    self.resolution.target_plan,
                    self.states.full_plan,
                    self.states.realization,
                    self.resolution.catalog,
                    on_exit=self.on_exit,
                    observer=meter,
                )
                record.record_probes("unwind", meter)
                report = record.unwind_report
                log_unwind(
                    dataclasses.replace(
                        report, errors=tuple((ref, self.secrets.mask(error)) for ref, error in report.errors)
                    )
                )
        finally:
            try:
                record.leaked_processes = ProcessWrapper.reap(owner=self)
            finally:
                try:
                    ProcessWrapper.deactivate(self, self._process_owner_token)
                    self._process_owner_token = None
                finally:
                    try:
                        self._write_artifacts()
                    finally:
                        try:
                            self._write_evidence()
                        finally:
                            self.phase = "closed"

    def close_problems(self) -> Failure | None:
        """The report for what went wrong while closing (a failing teardown hook, a node that would not
        dismantle), or None. Read after close(); closing itself never raises for these."""
        record = self.record
        failure = teardown_failure(
            record.teardown_results, record.unwind_report, self.evidence_dir, record.leaked_processes
        )
        return record.safe_failure(failure) if failure is not None else None

    # ---- what a caller reads ----

    @property
    def closed(self) -> bool:
        return self.phase == "closed"

    @property
    def target(self) -> Target:
        if self.handle is None:
            raise RuntimeError("the session has not resolved yet")
        return self.handle

    @property
    def packs(self) -> list:
        """(name, version, module) of each pack the target file loaded."""
        return self.resolution.packs if self.resolution is not None else []

    @property
    def catalog(self):
        """What the registered packs and the project declared: factories and actions, as data (None before
        `resolve()`)."""
        return self.resolution.catalog if self.resolution is not None else None

    @property
    def target_plan(self):
        """Gate 1's plan: which factory fills which role (None before `resolve()`)."""
        return self.resolution.target_plan if self.resolution is not None else None

    @property
    def action_plan(self):
        """Gate 2's plan: after `resolve()` every action the goals need; after `bring_up()` the ones that ran or
        were skipped as already holding (None before `resolve()`)."""
        if self.states is not None:
            return self.states.action_plan
        return self.resolution.action_plan if self.resolution is not None else None

    @property
    def full_plan(self):
        """Every action the goals, and every state reached so far, need (None before `resolve()`)."""
        return self.states.full_plan if self.states is not None else None

    @property
    def assumed(self) -> tuple:
        """What the current plan takes on faith, with owner and reason."""
        return self.states.assumed if self.states is not None else ()

    @property
    def observed(self) -> frozenset:
        """The states (`scope:state`) that held at the last probe."""
        return self.states.observed if self.states is not None else frozenset()

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.record.warnings

    @property
    def unwind_report(self) -> UnwindReport | None:
        """What `close()` dismantled (None before it ran)."""
        return self.record.unwind_report

    @property
    def preflight_report(self) -> gating.PreflightReport | None:
        """The collected requirements grouped by API family and exact consumer profile."""
        return self.record.preflight_report

    @property
    def gating_decisions(self) -> tuple:
        """((test id, GatingDecision), ...) of the last `select()`."""
        return tuple(self.record.gating_decisions)

    @property
    def evidence_dir(self) -> Path | None:
        """Where this run's files are, or None when it writes none (`artifacts="none"`)."""
        return None if self.artifacts == "none" else self.run_dir

    # ---- run files ----

    def _write_evidence(self) -> None:
        # Evidence is a report about the run, never a reason for closing to fail.
        if self.artifacts == "none":
            return
        try:
            from ..engine.evidence import write_evidence

            write_evidence(self.run_dir, self)
        except Exception as exc:  # noqa: BLE001
            self.record.log_event("evidence_failed", {"error": repr(exc)})

    def _write_artifacts(self) -> None:
        from ..artifacts import write_artifacts

        write_artifacts(self.run_dir, self, cache=self._artifact_cache, level=self.artifacts)


class DescribeResult:
    def __init__(self, session: Session):
        self._session = session

    @property
    def target_plan(self):
        return self._session.target_plan

    @property
    def action_plan(self):
        return self._session.action_plan

    def render(self) -> str:
        import json

        from ..engine.config import redact_target

        catalog = self._session.catalog
        tp = redact_target(self._session.target_plan, getattr(catalog, "config_schemas", {}))
        ap = self._session.action_plan
        return "\n".join(
            [
                "Plan, the roles of the target:",
                json.dumps(target_view(tp), indent=2) if tp is not None else "(none)",
                "Plan, the steps that bring it up:",
                json.dumps(display_json(label_steps(ap.to_json(), catalog)), indent=2) if ap is not None else "(none)",
                *(["Warnings:", *(f"  {w}" for w in self._session.warnings)] if self._session.warnings else []),
            ]
        )


def describe(roots=(), **opts) -> DescribeResult:
    opts["plan_only"] = True
    session = Session(roots, **opts)
    session.resolve()
    return DescribeResult(session)


@contextlib.contextmanager
def compose(roots=(), **opts):
    session = Session(roots, **opts)
    try:
        session.resolve()
        session.bring_up()
        yield session
    finally:
        session.close()
