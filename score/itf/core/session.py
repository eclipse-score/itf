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

Phase results accumulate here; artifacts are written even if a later phase fails, so partially
resolved runs remain inspectable.
"""

from __future__ import annotations

import dataclasses

import contextlib
import logging
import time
from pathlib import Path

from . import gating
from . import octo
from .engine.assumptions import describe_assumed
from .engine.bringup import ExecutionError, Observation, ProbeFailed, execute, observe
from .engine.close import SessionView, UnwindReport, run_startup_checks, run_teardown_hooks, unwind
from .engine.failure import Failure, bring_up_failure, checks_failure, teardown_failure
from .engine.realize import Realization
from .engine import packs as pack_loader
from .engine.metadata import LOCAL_PACK
from .engine.config import sensitive_values
from .engine.secrets import Secrets
from .engine.registry import ORIGINS, expand, register_modules
from .frontends import target_file
from .frontends.target_source import TargetSource, locate
from .engine.publish import publish, split_major
from .engine.render import render
from .engine.labels import label_steps, node_label
from .engine.scopes import ROOT, display, display_json
from .engine.log import (
    log_plan_warnings,
    log_checks,
    log_config_issues,
    log_bring_up_retry,
    log_nothing_to_bring_up,
    log_assumptions,
    describe_packs,
    log_packs,
    log_event,
    log_gating,
    log_phase,
    log_resolution,
    log_target_summary,
    log_teardown,
    log_unwind,
    log_drift,
)
from .process import ProcessWrapper
from .octo import GoalClaim
from .target_handle import Target, name_clashes, target_view

PRECEDENCE = ORIGINS
_RECORDED = frozenset({"state_probed", "action_started", "action_finished", "action_skipped"})


class ResolutionFailed(Exception):
    def __init__(self, gate: int, phase: str, diagnostics, rendered: str):
        super().__init__(rendered)
        self.gate = gate
        self.phase = phase
        self.diagnostics = diagnostics
        self.rendered = rendered


class NotReady(Exception):
    """Bring-up or a startup check failed. `failure` is the report to show a person (None when unknown)."""

    def __init__(self, message: str, failure=None):
        super().__init__(message)
        self.failure = failure


class ConfigValidationFailed(Exception):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__(
            display(
                "config validation failed:\n"
                + "\n".join(f"  {node_label(ref, provider)}: {message}" for ref, provider, message in self.issues)
            )
        )


class TargetNameClash(Exception):
    def __init__(self, clashes):
        self.clashes = tuple(clashes)
        super().__init__("ambiguous names on the target handle:\n" + "\n".join(f"  {c}" for c in self.clashes))


def _roots(roots) -> list:
    """Without pytest: `roots` are the project's policy; their `pytest_plugins` are followed as pytest would."""
    from .engine.registry import follow

    return list(follow((r, "policy") for r in roots))


def log_target_file(source, overrides) -> None:
    logging.getLogger("score.itf.core").info(
        "target file: %s%s",
        source.describe(),
        "".join(f"; override {o.describe()}" for o in overrides),
    )


GATING = ("skip", "fail")
REUSE = ("probe", "fresh")
ON_EXIT = ("unwind", "keep")
# What a run leaves in its run directory: nothing, what a person reads (the default), or every file ITF writes.
ARTIFACTS = ("none", "standard", "full")


def _one_of(name: str, value: str, allowed: tuple) -> str:
    if value not in allowed:
        raise ValueError(f"{name} is one of {', '.join(map(repr, allowed))}, not {value!r}")
    return value


class Session:
    """One run. `target` (a path, inline YAML/JSON text or a `TargetSource`) is the target file;
    `overrides` are further target files merged over it by role. Packs load from the factory labels the
    target file names; project capabilities and actions come from `roots` (the project's policy, their
    `pytest_plugins` followed) or `contributors`, the (module, origin) pairs a runner already loaded. Without a
    target file it is empty, which is valid. `gating` is `skip` (deselect) or `fail`, `reuse` is `probe` (keep what
    holds) or `fresh`, `on_exit` is `unwind` or `keep`. `definitions` (contract name -> `gating.Definition`, see
    `score.itf.core.adapters.definitions`) is optional: with it a plan warns about deprecated contracts; nothing
    needs it.

    Read it through `target` (the roles), `target_plan`, `action_plan`, `catalog` and `observed`."""

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
        self._roots = [roots] if isinstance(roots, str) else list(roots)
        self._contributors = contributors
        self.target_source: TargetSource | None = locate(target, "target=") if target is not None else None
        if isinstance(overrides, (str, TargetSource)):
            overrides = [overrides]
        self.override_sources = tuple(locate(o, "overrides=") for o in overrides)
        if self.override_sources and self.target_source is None:
            raise ValueError("overrides need a target file: Session(target=..., overrides=[...])")
        self.plan_only = plan_only
        self.gating = _one_of("gating", gating, GATING)
        self.reuse = _one_of("reuse", reuse, REUSE)
        self.on_exit = _one_of("on_exit", on_exit, ON_EXIT)
        self.artifacts = _one_of("artifacts", artifacts, ARTIFACTS)
        # A ${NAME} with no value: an error, or (planning only) a placeholder, for a compile that never builds.
        self.unset = _one_of("unset", unset, ("fail", "placeholder"))
        # How often bring-up may plan again when a step fails because a state that held stopped holding (a machine
        # that died while booting); any other failure ends bring-up at once.
        if not isinstance(bring_up_attempts, int) or bring_up_attempts < 1:
            raise ValueError(f"bring_up_attempts must be a whole number from 1, not {bring_up_attempts!r}")
        self.bring_up_attempts = bring_up_attempts
        if self.unset == "placeholder" and not plan_only:
            raise ValueError("unset='placeholder' is for plan_only sessions: nothing may be built from a placeholder")
        self.definitions = dict(definitions) if definitions else {}
        self.run_dir = Path(run_dir) if run_dir is not None else Path("itf-run")

        self._registry = None
        self.packs: list = []
        self._catalog = None
        self._setup_claims: frozenset = frozenset()
        self._init_claims: frozenset = frozenset()
        self._target_plan = None
        self._action_plan = None
        self._full_plan = None
        self._reached_goals: frozenset = frozenset()
        self._forgotten: frozenset = frozenset()  # states a discard made untrustworthy until the next reach
        self._realization = None
        self._factory_majors: dict = {}  # factory label -> the major it offers (absent: unknown)
        self._target_file = None
        self._compiled = None
        self._warnings: list = []
        self._scopes: frozenset = frozenset()
        self._last_observed: frozenset = frozenset()
        self._assumed: tuple = ()
        self._logged_assumptions: set[tuple[str, str, str, str]] = set()
        self._target: Target | None = None
        self._resolution_failure: ResolutionFailed | None = None
        self._config_issues: tuple = ()
        self._gating_decisions: list = []
        self._preflight_report: gating.PreflightReport | None = None
        self._run_report = None
        self._attempt = None  # the bring-up attempt running, for the evidence
        self._retries: tuple = ()  # one entry per bring-up attempt that lost a state and was planned again
        self._brought_up = False
        self.secrets = Secrets()  # the values of sensitive settings: masked wherever ITF shows text
        self._check_results: tuple = ()
        self._teardown_results: tuple = ()
        self._unwind_report: UnwindReport | None = None
        self._leaked_processes: tuple[str, ...] = ()
        self._ready = False
        self._closed = False
        self._artifact_cache: dict = {}
        self._probe_stats: dict = {}  # phase -> {count, ms, runs}
        self._drift: tuple = ()  # ({phase, dropped, appeared}, ...)
        self._events: tuple = ()  # ({phase, kind, t, ...}, ...): what the evidence record is built from
        self._failure_text: str = ""

    def _fail(self, gate: int, phase: str, diagnostics) -> None:
        roles = self._compiled.roles if self._compiled is not None else {}
        text = render(diagnostics, gate=gate, phase=phase, catalog=self._catalog, roles=roles)
        exc = ResolutionFailed(gate, phase, diagnostics, text)
        self._resolution_failure = exc
        log_resolution(gate, phase, False, diagnostics)
        raise exc

    def resolve(self) -> "Session":
        # Two gates, in order, because the second depends on the first. Gate 1 decides what must exist: which
        # factory fills which role, as a target plan. Gate 2 decides what must happen on it: the ordered actions
        # that make the goal states true. resolve() is a pure plan: it probes nothing and constructs nothing
        # (probing is the first thing bring_up does), so it is safe without hardware (`--itf-plan`, collection).
        log_phase("resolve")
        ProcessWrapper.activate(self)  # host processes started from here until close() are this session's
        try:
            doc = self._load_target_file()
            self._declare_parts(doc)
            self._plan_roles(doc)
            self._plan_actions()
            if self.plan_only:
                self._dry_run_check()
        finally:
            self._write_artifacts()
        return self

    def _load_target_file(self) -> dict:
        source = self.target_source
        doc = target_file.load_all(source, self.override_sources) if source else target_file.load({})
        self._target_file = doc
        if source is not None:
            log_target_file(source, self.override_sources)
        return doc

    def _declare_parts(self, doc: dict) -> None:
        """Load the packs the target file names, register them with the project's code, publish what they declare."""
        from .frontends.target_source import load_policies

        modules = target_file.pack_modules(doc)
        pack_entries = [pack_loader.load(name, modules) for name in target_file.packs_of(doc) if name != LOCAL_PACK]
        project = expand(self._contributors) if self._contributors is not None else _roots(self._roots)
        project = [*project, *_roots(load_policies(doc["policies"]))]
        self.packs = describe_packs(pack_entries)  # (name, version, module) of each pack the target file loaded
        log_packs(self.packs)
        self._registry = register_modules([*expand(pack_entries), *project])
        self._catalog = publish(self._registry)
        self._factory_majors = {l: f.major for l, f in self._catalog.factories.items() if f.major is not None}

    def _plan_roles(self, doc: dict) -> None:
        """Gate 1, then what is checked on its plan before anything else relies on it."""
        compiled = target_file.compile(doc, self._catalog, placeholders=self.unset == "placeholder")
        self._compiled = compiled
        self._setup_claims = compiled.setup | frozenset(self._catalog.providers)
        self._init_claims = compiled.init
        result = octo.resolve_target(self._setup_claims, precedence=PRECEDENCE)
        if not result.ok():
            self._fail(1, "capabilities", result.diagnostics)
        plan = self._target_plan = result.plan
        self._check_policy_expectations(plan, self._catalog)
        self._check_majors(plan, self._catalog)
        log_resolution(1, "capabilities", True, ())
        log_target_summary(plan)
        self._warn(gating.deprecations(plan, self.definitions))
        self._check_settings(plan)
        self._scopes = frozenset(s for s in compiled.roles if s != ROOT)
        # `target.<x>` must mean one thing: a role named like a scope or a handle member would be
        # ambiguous, so it is rejected up front instead of resolving to whichever wins.
        clashes = name_clashes(plan, self._scopes)
        if clashes:
            raise TargetNameClash(clashes)
        self._realization = Realization(plan, owner=self)
        self._target = Target(self, self._scopes)

    def _check_settings(self, plan) -> None:
        """Settings are validated against each factory's schema here, between the gates, so a typo in a
        target file fails at plan time with the role named, not when the factory is first used."""
        issues = []
        for node in plan.nodes:
            schema = self._catalog.config_schemas.get(node.provider)
            if schema is not None:
                issues.extend((node.ref, node.provider, message) for message in schema.validate(dict(node.config)))
        self._config_issues = tuple(issues)
        for value in sensitive_values(plan, self._catalog.config_schemas):
            self.secrets.add(value)
        self.secrets.install()
        if issues:
            log_config_issues(issues)
            raise ConfigValidationFailed(issues)

    def _plan_actions(self) -> None:
        """Gate 2 with nothing observed: every action the goals need."""
        result = octo.resolve_actions(self._init_claims, self._target_plan, precedence=PRECEDENCE)
        if not result.ok():
            self._fail(2, "states", result.diagnostics)
        self._full_plan = self._action_plan = result.plan
        log_resolution(2, "states", True, ())
        self._assumed = describe_assumed(result.plan, self._init_claims)
        self._log_new_assumptions()

    def _log_new_assumptions(self) -> None:
        new = []
        for assumption in self._assumed:
            values = tuple(assumption.get(name, "") for name in ("state", "owner", "reason", "origin"))
            if values in self._logged_assumptions:
                continue
            self._logged_assumptions.add(values)
            new.append({**assumption, "owner": self.secrets.mask(values[1]), "reason": self.secrets.mask(values[2])})
        log_assumptions(new)

    def _check_policy_expectations(self, plan, catalog) -> None:
        diagnostics = []
        unknown = []
        for expectation in catalog.expectations:
            contract, major = split_major(expectation.contract)
            for node in plan.nodes:
                if node.contract != contract:
                    continue
                offered = catalog.factories[node.provider].major
                if major is not None:
                    if offered is None:
                        unknown.append(
                            f"{expectation.origin}: {display(node.ref)} ({node.provider}) has no declared major; "
                            f"policy requires {expectation.contract}"
                        )
                        continue
                    if offered != major:
                        continue
                diagnostics.extend(
                    dataclasses.replace(
                        diagnostic,
                        evidence=tuple(
                            sorted(
                                (
                                    *diagnostic.evidence,
                                    ("policy", expectation.origin),
                                    ("contract", expectation.contract),
                                )
                            )
                        ),
                    )
                    for diagnostic in octo.shape_mismatches(node.ref, node.gives, expectation.shape, gate=1)
                )
        if unknown:
            message = "policy contract major unknown:\n  " + "\n  ".join(unknown)
            if diagnostics:
                message += "\n" + render(
                    diagnostics,
                    gate=1,
                    phase="policy expectations",
                    catalog=catalog,
                    roles=self._compiled.roles,
                )
            raise target_file.TargetFileError(message)
        if diagnostics:
            self._fail(1, "policy expectations", tuple(diagnostics))

    def _check_majors(self, plan, catalog) -> None:
        """When a factory offers `@major` and a slot expects one, they must agree."""
        problems = []
        for node in plan.nodes:
            expected = catalog.factories[node.provider].need_majors
            for slot, ref in node.bindings:
                provider = plan.node(ref).provider
                offered = catalog.factories[provider].major
                if slot in expected and offered is not None and expected[slot] != offered:
                    problems.append(
                        f"{display(node.ref)} ({node.provider}) expects its {slot} at @{expected[slot]} but "
                        f"{display(ref)} ({provider}) offers @{offered}"
                    )
        if problems:
            raise target_file.TargetFileError("contract major mismatch:\n  " + "\n  ".join(problems))

    def _warn(self, messages) -> None:
        fresh = [m for m in messages if m not in self._warnings]
        if fresh:
            self._warnings.extend(fresh)
            log_plan_warnings(fresh)

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self._warnings)

    def _observe_and_plan(self) -> Observation:
        """Observe the full plan, then plan the actions (gate 2) for what does not hold yet: a state that already
        holds is not run again. With reuse == "fresh" nothing is observed and every planned action runs."""
        if self.reuse == "fresh":
            return Observation(frozenset(), ())
        meter = self._meter(log_event)
        observation = observe(self._full_plan, self._realization, observer=meter)
        self._record_probes("before_bring_up", meter)
        delta = octo.resolve_actions(
            self._init_claims, self._target_plan, precedence=PRECEDENCE, observed_states=observation.holds
        )
        if not delta.ok():
            self._fail(2, "states", delta.diagnostics)
        self._action_plan = delta.plan
        self._assumed = describe_assumed(delta.plan, self._init_claims)
        return observation

    def _lost_during(self, exc: ExecutionError, observation: Observation) -> frozenset:
        """The states that held during this bring-up (observed before it, or made true by a step that ran) and no
        longer hold: what makes a failed bring-up worth planning again. Its probes are recorded like any other."""
        delivered = {state for step in self._action_plan.steps if step.key in exc.executed for state in step.delivers}
        held = set(observation.holds) | delivered
        meter = self._meter()
        now = observe(self._full_plan, self._realization, observer=meter).holds
        self._record_probes("bring_up_lost_check", meter)
        return frozenset(held - now)

    def _dry_run_check(self) -> None:
        """A dry run resolves every `impl`, teardown and probe reference; constructs nothing."""
        extra = tuple(s.impl for s in self._action_plan.steps)
        extra += tuple(probe for s in self._action_plan.steps for _, probe in s.state_probes())
        self._realization.resolve_all(extra_impls=extra)

    def select(self, requirements: dict) -> dict:
        """`requirements`: test id -> tuple[Requirement, ...]. Returns test id -> GatingDecision.
        A requirement without `scope` is checked against the root scope only. Every requirement is
        evaluated; `preflight_report` retains grouped profiles and diagnostics even for deselected tests."""
        self._preflight_report = gating.preflight(requirements, self._target_plan, self._factory_majors)
        decisions = self._preflight_report.decisions
        self._gating_decisions = list(decisions.items())
        log_gating(decisions, self._preflight_report)
        self._write_artifacts()
        return decisions

    def probe(self, states: frozenset | None = None) -> frozenset:
        """Run the probes of the full plan (of `states` only, qualified `scope:state`, when given) and return what
        holds. `itf down` uses it to see what a fresh session finds; nothing is built that no probe needs."""
        meter = self._meter()
        observation = observe(self._full_plan, self._realization, states=states, observer=meter)
        self._record_probes("probe", meter)
        self._last_observed = (
            observation.holds if states is None else (self._last_observed - states) | observation.holds
        )
        return observation.holds

    def bring_up(self) -> None:
        if self.plan_only:
            raise RuntimeError("a plan_only session does not bring up")
        self._brought_up = True
        # Bring-up probes first (a state already holding is reused), then runs the delta. Startup checks
        # (itf_verify) run last and only after the states hold, so a check failure means the target is
        # unhealthy, not that it is still being built. Essential check failures stop the session before any
        # test runs.
        log_phase("bring-up")
        if not self._action_plan.steps:
            log_nothing_to_bring_up()
        try:
            for attempt in range(1, self.bring_up_attempts + 1):
                self._attempt = attempt  # tags this attempt's events, so the evidence tells attempts apart
                observation = self._observe_and_plan()
                self._last_observed = observation.holds
                meter = self._meter(log_event)
                failed = None
                try:
                    self._run_report = execute(self._action_plan, self._realization, observation, observer=meter)
                except (ExecutionError, ProbeFailed) as exc:
                    failed = exc
                finally:
                    self._record_probes("bring_up", meter)
                    self._write_artifacts()
                if failed is None:
                    break
                lost = self._lost_during(failed, observation) if attempt < self.bring_up_attempts else frozenset()
                error = self.secrets.mask(display(str(failed)))
                if not lost:
                    failure = self._masked(
                        bring_up_failure(failed, self._action_plan, self._target_plan, self.evidence_dir)
                    )
                    self._failure_text = failure.render()
                    self._write_artifacts()
                    raise NotReady(error, failure) from failed
                log_bring_up_retry(attempt, self.bring_up_attempts, error, sorted(lost))
                self._retries = self._retries + ({"attempt": attempt, "lost": sorted(lost), "error": error},)
                self._write_artifacts()
        finally:
            self._attempt = None

        self._last_observed = self._observe_and_check("after_bring_up", self._run_report.holds)
        log_phase("startup checks")
        view = SessionView(self)
        self._check_results = run_startup_checks(self._registry, view)
        log_checks(self._check_results)
        self._write_artifacts()
        failing = [c for c in self._check_results if c.essential and not c.ok]
        if failing:
            failure = self._masked(checks_failure(self._check_results, self.evidence_dir))
            self._failure_text = failure.render()
            raise NotReady(
                f"{len(failing)} essential startup check(s) failed: {', '.join(c.name for c in failing)}", failure
            )
        self._ready = True

    @property
    def target(self) -> Target:
        if self._target is None:
            raise RuntimeError("the session has not resolved yet")
        return self._target

    @property
    def target_plan(self):
        """Gate 1's plan: which factory fills which role (None before `resolve()`)."""
        return self._target_plan

    @property
    def action_plan(self):
        """Gate 2's plan: after `resolve()` every action the goals need; after `bring_up()` the ones that ran or
        were skipped as already holding (None before `resolve()`)."""
        return self._action_plan

    @property
    def catalog(self):
        """What the registered packs and the project declared: factories and actions, as data (None before
        `resolve()`)."""
        return self._catalog

    @property
    def unwind_report(self) -> UnwindReport | None:
        """What `close()` dismantled (None before it ran)."""
        return self._unwind_report

    @property
    def preflight_report(self) -> gating.PreflightReport | None:
        """The collected requirements grouped by API family and exact consumer profile."""
        return self._preflight_report

    @property
    def gating_decisions(self) -> tuple:
        """((test id, GatingDecision), ...) of the last `select()`."""
        return tuple(self._gating_decisions)

    @property
    def observed(self) -> frozenset:
        """The states (`scope:state`) that held at the last probe."""
        return self._last_observed

    def reach(self, *states: str, assume: tuple[str, ...] = (), reason: str = "", owner: str = ""):
        """Re-plan and execute the delta to reach `states`: `token` or `:token` is the root scope,
        `dev1:token` a device. `assume` (same form) bypasses a dependency's producer for this call
        only, without evidence that it holds; the plan records which ids were taken on faith and,
        via `owner`/`reason`, who said so.
        """
        return self._reach(states, assume=assume, reason=reason, owner=owner)

    def renew(self, *nodes: str):
        """Rebuild nodes from scratch, then reach every goal so far again: `name` or `.name` is a
        root node, `dev1.name` a device's. Each node and every realized node bound to it is
        dismantled; a state delivered through one of them, or requiring such a state, is not
        taken as holding even if its probe says so, so its producer runs again.
        """
        # Renewal is a primitive, not a mode: the caller decides when (a fixture, a test). Nothing in ITF renews
        # on its own, so ITF never fights pytest's own fixture scoping.
        log_phase(f"renew {', '.join(nodes)}")
        self.discard(*nodes)
        return self._reach(())

    def discard(self, *roles: str) -> None:
        """Dismantle roles (and every built role bound to them) without reaching anything: the next access
        builds them afresh, so a caller may adjust a new object before `reach`. The states whose evidence ran
        through a dismantled role are forgotten until the next `reach` delivers them again."""
        refs = [n[1:] if n.startswith(".") else n for n in roles]
        refs = [r if "." in r else f"{ROOT}.{r}" for r in refs]
        for ref in refs:
            if not self._realization.has(ref):
                raise KeyError(f"target has no role {ref!r}")
        dismantled = frozenset(self._realization.discard(refs))
        # A probe cannot be trusted for a state whose evidence ran through a dismantled role (it may read state
        # that lives outside the new object, e.g. a port the old container still held). Such states, and whatever
        # requires them, are re-delivered by their actions rather than taken as holding.
        self._forgotten |= self._tainted_by(dismantled)

    def _tainted_by(self, dismantled: frozenset) -> frozenset:
        """The states whose evidence ran through a dismantled role, and every state that requires one."""
        resolve = self._target_plan.resolve
        steps = self._full_plan.steps
        tainted = {
            d for step in steps if any(resolve(ref) in dismantled for _, ref in step.uses) for d in step.delivers
        }
        grew = True
        while grew:
            grew = False
            for step in steps:
                if set(step.requires) & tainted and not set(step.delivers) <= tainted:
                    tainted.update(step.delivers)
                    grew = True
        return frozenset(tainted)

    def _qualify(self, state: str) -> str:
        """`state` (`token`, `:token` or `scope:token`) as `scope:token`."""
        scope, _, token = state.rpartition(":")
        return f"{scope or ROOT}:{token}"

    def _check_scopes(self, qualified) -> None:
        known = {ROOT, *self.target.scopes()}
        unknown = sorted({r.split(":", 1)[0] for r in qualified} - known)
        if unknown:
            raise KeyError(
                f"target has no scope {', '.join(map(repr, unknown))}; "
                f"scopes: {', '.join(self.target.scopes()) or '(none)'}"
            )

    def _plan_delta(self, claims, assumed_ids: frozenset, observed: frozenset):
        result = octo.resolve_actions(
            claims, self._target_plan, precedence=PRECEDENCE, observed_states=observed, assumed_states=assumed_ids
        )
        if not result.ok():
            self._fail(2, "states", result.diagnostics)
        return result.plan

    def _reach(self, states, *, assume=(), reason: str = "", owner: str = "", forget: frozenset = frozenset()):
        wanted = [self._qualify(s) for s in states]
        assumed_ids = frozenset(self._qualify(s) for s in assume)
        self._check_scopes([*wanted, *assumed_ids])
        if wanted:
            log_phase(f"reach {', '.join(wanted)}")
        by_scope: dict[str, set] = {}
        for ref in wanted:
            scope, token = ref.split(":", 1)
            by_scope.setdefault(scope, set()).add(token)
        # The project's own code asks for these (a test, a fixture): they join the target file's goals and every
        # goal reached so far, for the probes and for the delta alike. A state pruned from one delta would go
        # unobserved, and a state reached earlier would not be delivered again after a renewal.
        self._reached_goals |= {GoalClaim(scope=s, states=frozenset(t), origin="policy") for s, t in by_scope.items()}
        claims = self._init_claims | self._reached_goals
        self._full_plan = self._plan_delta(claims, assumed_ids, frozenset())
        meter = self._meter()
        observation = observe(self._full_plan, self._realization, observer=meter)
        self._record_probes("reach_before", meter)
        forget = forget | self._forgotten
        if forget:
            observation = Observation(observation.holds - forget, observation.errors)
        plan = self._plan_delta(claims, assumed_ids, observation.holds)
        log_resolution(2, "states", True, ())
        meter = self._meter(log_event)
        try:
            report = execute(plan, self._realization, observation, observer=meter)
        finally:
            self._record_probes("reach_verify", meter)
        self._action_plan = plan
        self._assumed = describe_assumed(
            plan, claims, request_ids=assumed_ids, request_owner=owner, request_reason=reason
        )
        self._log_new_assumptions()
        self._run_report = report
        self._forgotten = frozenset()
        self._last_observed = self._observe_and_check("after_reach", report.holds)
        self._write_artifacts()
        return report

    def _meter(self, forward=None):
        """An observer that counts probe calls and their time, then forwards every event."""
        counts = {"count": 0, "ms": 0.0}
        events: list = []

        def observer(kind: str, data: dict) -> None:
            if kind in _RECORDED:
                events.append({"kind": kind, "t": time.time(), **data})
            if kind == "state_probed":
                counts["count"] += 1
                counts["ms"] += data.get("ms", 0.0)
            if forward is not None:
                forward(kind, data)

        observer.counts = counts
        observer.events = events
        return observer

    def _record_probes(self, phase: str, meter) -> None:
        # replaced, not mutated: the artifact cache compares by identity
        attempt = {"attempt": self._attempt} if self._attempt is not None else {}
        self._events = self._events + tuple({"phase": phase, **attempt, **e} for e in meter.events)
        meter.events.clear()
        prev = self._probe_stats.get(phase, {"count": 0, "ms": 0.0, "runs": 0})
        self._probe_stats = {
            **self._probe_stats,
            phase: {
                "count": prev["count"] + meter.counts["count"],
                "ms": round(prev["ms"] + meter.counts["ms"], 3),
                "runs": prev["runs"] + 1,
            },
        }

    def _observe_and_check(self, phase: str, expected: frozenset) -> frozenset:
        """Re-probe the full plan and report drift: a probed state that should hold and does not
        (dropped, e.g. an undeclared side effect) or holds but was not expected (appeared)."""
        meter = self._meter()
        actual = observe(self._full_plan, self._realization, observer=meter).holds
        self._record_probes(phase, meter)
        probed = {d for s in self._full_plan.steps for d, _ in s.state_probes()}
        dropped, appeared = sorted((expected - actual) & probed), sorted((actual - expected) & probed)
        if dropped or appeared:
            entry = {"phase": phase, "dropped": dropped, "appeared": appeared}
            self._drift = self._drift + (entry,)
            log_drift(entry)
        return actual

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Order matters: teardown hooks first, while the target still runs (they collect evidence from it),
        # then unwind dismantles what was built. Idempotent, so an error path and the normal path may both
        # call close().
        log_phase("close")
        if self._registry is not None:
            view = SessionView(self)
            self._teardown_results = run_teardown_hooks(self._registry, view)
            log_teardown(self._teardown_results)
        if self._target_plan is not None and self._full_plan is not None and self._realization is not None:
            meter = self._meter()
            self._unwind_report = unwind(
                self._target_plan,
                self._full_plan,
                self._realization,
                self._catalog,
                on_exit=self.on_exit,
                observer=meter,
            )
            self._record_probes("unwind", meter)
            log_unwind(self._unwind_report)
        # Anything a provider, a test or a failed teardown left running is stopped now, and reported: a run
        # must not leave host processes behind, and a leak is a defect in whoever started it.
        self._leaked_processes = ProcessWrapper.reap(owner=self)
        ProcessWrapper.deactivate(self)
        self._write_artifacts()
        self._write_evidence()
        self.secrets.uninstall()

    def close_problems(self) -> Failure | None:
        """The report for what went wrong while closing (a failing teardown hook, a node that would not
        dismantle), or None. Read after close(); closing itself never raises for these."""
        failure = teardown_failure(
            self._teardown_results, self._unwind_report, self.evidence_dir, self._leaked_processes
        )
        return self._masked(failure) if failure is not None else None

    def _masked(self, failure: Failure) -> Failure:
        """`failure` with every secret of this session masked."""
        rows = tuple((label, self.secrets.mask(value)) for label, value in failure.rows)
        return dataclasses.replace(failure, rows=rows, hints=tuple(self.secrets.mask(h) for h in failure.hints))

    def _write_evidence(self) -> None:
        # Evidence is a report about the run, never a reason for closing to fail.
        if self.artifacts == "none":
            return
        try:
            from .engine.evidence import write_evidence

            write_evidence(self.run_dir, self)
        except Exception as exc:  # noqa: BLE001
            log_event("evidence_failed", {"error": repr(exc)})

    @property
    def evidence_dir(self) -> Path | None:
        """Where this run's files are, or None when it writes none (`artifacts="none"`)."""
        return None if self.artifacts == "none" else self.run_dir

    def _write_artifacts(self) -> None:
        from .artifacts import write_artifacts

        write_artifacts(self.run_dir, self, cache=self._artifact_cache, level=self.artifacts)


class DescribeResult:
    def __init__(self, session: Session):
        self._session = session

    @property
    def target_plan(self):
        return self._session._target_plan

    @property
    def action_plan(self):
        return self._session._action_plan

    def render(self) -> str:
        import json
        from .engine.config import redact_target

        catalog = self._session._catalog
        tp = redact_target(self._session._target_plan, getattr(catalog, "config_schemas", {}))
        ap = self._session._action_plan
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
