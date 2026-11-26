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
"""The states of a resolved target at run time: what holds, and what runs to make the goals hold.

Every operation here has the same shape: observe (probes), plan the delta (gate 2 over what does not hold), run it,
and observe again to report drift. Bring-up, `reach`, `renew` and `discard` differ only in what they ask for and
what they stop trusting.
"""

from __future__ import annotations

from ..engine.assumptions import describe_assumed
from ..engine.bringup import ExecutionError, Observation, ProbeFailed, execute, observe
from ..engine.failure import bring_up_failure
from ..engine.log import log_assumptions, log_bring_up_retry, log_nothing_to_bring_up, log_phase, log_resolution
from ..engine.realize import Realization
from ..engine.scopes import ROOT, display
from ..octo import GoalClaim
from .errors import NotReady
from .record import RunRecord
from .resolution import Resolution


def qualify(state: str) -> str:
    """`state` (`token`, `:token` or `scope:token`) as `scope:token`."""
    scope, _, token = state.rpartition(":")
    return f"{scope or ROOT}:{token}"


class TargetStates:
    """The run-time half of a session. `realization` builds the roles; `resolution` plans; `record` keeps what
    happened. `reuse` is "probe" (keep what holds) or "fresh" (run every action)."""

    def __init__(self, resolution: Resolution, realization: Realization, record: RunRecord, *, reuse: str):
        self.resolution = resolution
        self.realization = realization
        self.record = record
        self.reuse = reuse
        self.full_plan = resolution.action_plan  # every action the goals (and every state reached so far) need
        self.action_plan = resolution.action_plan  # the delta that ran last (or would run, before bring-up)
        self.assumed: tuple = ()  # what the last plan takes on faith, with owner and reason
        self.observed: frozenset = frozenset()  # what held at the last probe
        self._reached_goals: frozenset = frozenset()  # states asked for with reach(), kept as goals from then on
        self._forgotten: frozenset = frozenset()  # states a discard made untrustworthy until the next reach
        self._logged_assumptions: set[tuple[str, str, str, str]] = set()
        self._set_assumed(describe_assumed(self.action_plan, resolution.init_claims))

    # ---- observing ----

    def probe(self, states: frozenset | None = None) -> frozenset:
        """Run the probes of the full plan (of `states` only, qualified `scope:state`, when given) and return what
        holds."""
        meter = self.record.meter()
        observation = observe(self.full_plan, self.realization, states=states, observer=meter)
        self.record.record_probes("probe", meter)
        self.observed = observation.holds if states is None else (self.observed - states) | observation.holds
        return observation.holds

    def observe_and_check(self, phase: str, expected: frozenset) -> frozenset:
        """Re-probe the full plan and report drift: a probed state that should hold and does not
        (dropped, e.g. an undeclared side effect) or holds but was not expected (appeared)."""
        meter = self.record.meter()
        actual = observe(self.full_plan, self.realization, observer=meter).holds
        self.record.record_probes(phase, meter)
        probed = {d for s in self.full_plan.steps for d, _ in s.state_probes()}
        dropped, appeared = sorted((expected - actual) & probed), sorted((actual - expected) & probed)
        if dropped or appeared:
            self.record.add_drift(phase, dropped, appeared)
        self.observed = actual
        return actual

    # ---- bring-up ----

    def bring_up(self, attempts: int, *, evidence_dir, written=lambda: None) -> None:
        """Probe, then run the delta; plan again (up to `attempts` times) when a step failed because a state that
        held stopped holding. Any other failure raises NotReady with the failure report. `written` is called
        whenever the record changed, so a failed run still leaves its files."""
        log_phase("bring-up")
        if not self.action_plan.steps:
            log_nothing_to_bring_up()
        record = self.record
        try:
            for attempt in range(1, attempts + 1):
                record.attempt = attempt  # tags this attempt's events, so the evidence tells attempts apart
                observation = self._observe_and_plan()
                self.observed = observation.holds
                meter = record.meter(record.log_event)
                failed = None
                try:
                    record.run_report = execute(self.action_plan, self.realization, observation, observer=meter)
                except (ExecutionError, ProbeFailed) as exc:
                    failed = exc
                finally:
                    record.record_probes("bring_up", meter)
                    written()
                if failed is None:
                    break
                lost = self._lost_during(failed, observation) if attempt < attempts else frozenset()
                error = record.secrets.mask(display(str(failed)))
                if not lost:
                    failure = record.safe_failure(
                        bring_up_failure(failed, self.action_plan, self.resolution.target_plan, evidence_dir)
                    )
                    record.failure_text = failure.render()
                    written()
                    raise NotReady(error, failure) from failed
                log_bring_up_retry(attempt, attempts, error, sorted(lost))
                record.add_retry(attempt, sorted(lost), error)
                written()
        finally:
            record.attempt = None
        self.observe_and_check("after_bring_up", record.run_report.holds)

    def _observe_and_plan(self) -> Observation:
        """Observe the full plan, then plan the actions (gate 2) for what does not hold yet: a state that already
        holds is not run again. With reuse == "fresh" nothing is observed and every planned action runs."""
        if self.reuse == "fresh":
            observation = Observation(frozenset(), ())
            self.record.pre_observation = observation
            return observation
        meter = self.record.meter(self.record.log_event)
        observation = observe(self.full_plan, self.realization, observer=meter)
        self.record.pre_observation = observation
        self.record.record_probes("before_bring_up", meter)
        self.action_plan = self.resolution.plan(self.resolution.init_claims, observed=observation.holds)
        self._set_assumed(describe_assumed(self.action_plan, self.resolution.init_claims), log=False)
        return observation

    def _lost_during(self, exc: ExecutionError, observation: Observation) -> frozenset:
        """The states that held during this bring-up (observed before it, or made true by a step that ran) and no
        longer hold: what makes a failed bring-up worth planning again. Its probes are recorded like any other."""
        delivered = {state for step in self.action_plan.steps if step.key in exc.executed for state in step.delivers}
        held = set(observation.holds) | delivered
        meter = self.record.meter()
        now = observe(self.full_plan, self.realization, observer=meter).holds
        self.record.record_probes("bring_up_lost_check", meter)
        return frozenset(held - now)

    # ---- reach, discard ----

    def reach(self, states, *, scopes, assume=(), reason: str = "", owner: str = ""):
        """Re-plan and execute the delta to reach `states` (and every goal so far); see `Session.reach`."""
        wanted = [qualify(s) for s in states]
        assumed_ids = frozenset(qualify(s) for s in assume)
        _check_scopes([*wanted, *assumed_ids], scopes)
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
        claims = self.resolution.init_claims | self._reached_goals
        self.full_plan = self.resolution.plan(claims, assumed=assumed_ids)
        meter = self.record.meter()
        observation = observe(self.full_plan, self.realization, observer=meter)
        self.record.record_probes("reach_before", meter)
        for step, error in observation.errors:
            self.record.log_event("state_probed", {"step": step, "error": error})
        if self._forgotten:
            observation = Observation(observation.holds - self._forgotten, observation.errors)
        plan = self.resolution.plan(claims, observed=observation.holds, assumed=assumed_ids)
        log_resolution(2, "states", True, ())
        meter = self.record.meter(self.record.log_event)
        try:
            report = execute(plan, self.realization, observation, observer=meter)
        finally:
            self.record.record_probes("reach_verify", meter)
        self.action_plan = plan
        self._set_assumed(
            describe_assumed(plan, claims, request_ids=assumed_ids, request_owner=owner, request_reason=reason)
        )
        self.record.run_report = report
        self._forgotten = frozenset()
        self.observe_and_check("after_reach", report.holds)
        return report

    def discard(self, roles) -> None:
        """Dismantle roles (and every built role bound to them); see `Session.discard`."""
        refs = [n[1:] if n.startswith(".") else n for n in roles]
        refs = [r if "." in r else f"{ROOT}.{r}" for r in refs]
        for ref in refs:
            if not self.realization.has(ref):
                raise KeyError(f"target has no role {ref!r}")
        dismantled = frozenset(self.realization.discard(refs))
        # A probe cannot be trusted for a state whose evidence ran through a dismantled role (it may read state
        # that lives outside the new object, e.g. a port the old container still held). Such states, and whatever
        # requires them, are re-delivered by their actions rather than taken as holding.
        self._forgotten |= self._tainted_by(dismantled)

    def _tainted_by(self, dismantled: frozenset) -> frozenset:
        """The states whose evidence ran through a dismantled role, and every state that requires one."""
        resolve = self.resolution.target_plan.resolve
        steps = self.full_plan.steps
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

    # ---- assumptions ----

    def _set_assumed(self, assumed: tuple, *, log: bool = True) -> None:
        self.assumed = assumed
        if not log:
            return
        secrets = self.record.secrets
        new = []
        for assumption in assumed:
            values = tuple(assumption.get(name, "") for name in ("state", "owner", "reason", "origin"))
            if values in self._logged_assumptions:
                continue
            self._logged_assumptions.add(values)
            new.append({**assumption, "owner": secrets.mask(values[1]), "reason": secrets.mask(values[2])})
        log_assumptions(new)


def _check_scopes(qualified, scopes) -> None:
    known = {ROOT, *scopes}
    unknown = sorted({r.split(":", 1)[0] for r in qualified} - known)
    if unknown:
        raise KeyError(f"target has no scope {', '.join(map(repr, unknown))}; scopes: {', '.join(scopes) or '(none)'}")
