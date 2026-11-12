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
"""Probe before executing to reuse states that already hold without construction side effects.

Actions receive only their `uses`
slots plus `config={}` — the plan carries no config for state contracts, so there is no clean
source for one (see the final report's deviations section).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .realize import default_resolver


class ExecutionError(Exception):
    """A step's action raised. `step`, `executed` and `skipped` say how far bring-up got; `cause` is the
    original exception, so a report can show what happened rather than only that something did."""

    step = None
    executed: tuple = ()
    skipped: tuple = ()
    cause: BaseException | None = None


class ProbeFailed(ExecutionError):
    """An action returned cleanly but its probe reports the state does not hold (`states` names them)."""

    states: tuple = ()


@dataclass(frozen=True)
class Observation:
    holds: frozenset  # {"scope:token", ...}
    errors: tuple  # (("scope:token", repr(exc)), ...)


# Probe before executing: a state that already holds (a container left running, a port already open) is
# not rebuilt. Probes must be cheap and side-effect free; a probe that raises counts as "does not hold"
# and is reported, never fatal, so a half-dead target is rebuilt instead of trusted.
def observe(
    action_plan, realization, *, states: frozenset | None = None, resolver=default_resolver, observer=None
) -> Observation:
    holds: set[str] = set()
    errors: list[tuple[str, str]] = []
    for step in action_plan.steps:
        for probe, delivered in _by_probe(step):
            relevant = delivered if states is None else tuple(d for d in delivered if d in states)
            if not relevant:
                continue
            try:
                kwargs = {slot: realization.get(ref) for slot, ref in step.uses}
                t0 = time.perf_counter()
                ok = resolver(probe)(**kwargs)
            except Exception as exc:
                errors.append((step.key, repr(exc)))
                if observer:
                    observer(
                        "state_probed", {"step": step.key, "states": list(relevant), "ok": None, "error": repr(exc)}
                    )
                continue
            if observer:
                observer(
                    "state_probed",
                    {
                        "step": step.key,
                        "states": list(relevant),
                        "ok": bool(ok),
                        "ms": (time.perf_counter() - t0) * 1e3,
                    },
                )
            if ok:
                holds.update(relevant)
    return Observation(frozenset(holds), tuple(errors))


def _by_probe(step) -> list[tuple[str, tuple[str, ...]]]:
    """[(probe ref, states it is evidence for), ...] in a stable order; a step with several
    delivered states may hold several probes (collapsed contracts each keep their own)."""
    grouped: dict[str, list[str]] = {}
    for state, probe in step.state_probes():
        grouped.setdefault(probe, []).append(state)
    return [(probe, tuple(sorted(states))) for probe, states in sorted(grouped.items())]


def _located(error, step, executed, skipped, cause):
    error.step, error.executed, error.skipped, error.cause = step, tuple(executed), tuple(skipped), cause
    return error


@dataclass(frozen=True)
class RunReport:
    executed: tuple[str, ...]
    skipped: tuple[str, ...]
    events: tuple[tuple[str, dict], ...]
    holds: frozenset = frozenset()  # what should hold afterwards: observed + verified - invalidated


def execute(
    action_plan, realization, observation: Observation, *, resolver=default_resolver, observer=None
) -> RunReport:
    observed = set(observation.holds)
    executed: list[str] = []
    skipped: list[str] = []
    events: list[tuple[str, dict]] = []

    def emit(kind: str, **data):
        events.append((kind, data))
        if observer:
            observer(kind, data)

    for step in action_plan.steps:
        # Only a step with a probe can be skipped: without one there is no evidence the state still holds,
        # so the action always runs.
        if step.probe and all(d in observed for d in step.delivers):
            skipped.append(step.key)
            emit("action_skipped", step=step.key, reason="observed")
            continue

        kwargs = {}
        for slot, ref in step.uses:
            kwargs[slot] = realization.get(ref)
            emit("node_realized", ref=ref)

        emit("action_started", step=step.key)
        try:
            resolver(step.impl)(**kwargs)
        except Exception as exc:
            emit("action_finished", step=step.key, ok=False, error=repr(exc))
            raise _located(ExecutionError(f"{step.key}: {exc}"), step, executed, skipped, exc) from exc
        emit("action_finished", step=step.key, ok=True)

        # An action that breaks other states (a restart invalidates the connection) removes them from the
        # evidence, so later steps that need them are not skipped on stale information.
        for token in step.invalidates:
            observed.discard(token)
        for token in step.delivers:
            observed.add(token)

        # Trust, but verify: an action that returned cleanly must also pass its probe, otherwise bring-up
        # fails here with the state named, not three tests later with a confusing connection error.
        failed: list[str] = []
        for probe, delivered in _by_probe(step):
            t0 = time.perf_counter()
            try:
                ok = bool(resolver(probe)(**kwargs))
            except Exception:
                ok = False
            emit("state_probed", step=step.key, states=list(delivered), ok=ok, ms=(time.perf_counter() - t0) * 1e3)
            if not ok:
                failed.extend(delivered)
        if failed:
            for token in failed:
                observed.discard(token)
            error = _located(
                ProbeFailed(f"{step.key}: action returned but the probe for {', '.join(failed)} reports false"),
                step,
                executed,
                skipped,
                None,
            )
            error.states = tuple(failed)
            raise error

        executed.append(step.key)

    return RunReport(tuple(executed), tuple(skipped), tuple(events), frozenset(observed))
