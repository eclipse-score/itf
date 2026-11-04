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
"""Startup checks, teardown hooks, unwind."""

from __future__ import annotations

from dataclasses import dataclass

from .bringup import observe
from .realize import default_resolver


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    essential: bool = True


class SessionView:
    """Passed to `itf_verify` and `itf_teardown` implementations."""

    def __init__(self, session):
        self._session = session
        self._checks: list[CheckResult] = []

    def check(self, name: str, ok: bool, *, detail: str = "", essential: bool = True) -> None:
        self._checks.append(CheckResult(name, bool(ok), detail, essential))

    @property
    def target(self):
        return self._session.target

    @property
    def evidence_dir(self):
        return self._session.evidence_dir


# A hook that records no check passes by not raising; one that raises is a failed essential check named
# after the hook, so a setup problem always surfaces as a named failure before the first test runs.
def run_startup_checks(registry, view: SessionView) -> tuple[CheckResult, ...]:
    results: list[CheckResult] = []
    for hi in registry.pm.hook.itf_verify.get_hookimpls():
        qualname = f"{hi.plugin.__name__}.{hi.function.__name__}"
        view._checks = []
        try:
            hi.function(view)
        except Exception as exc:
            results.append(CheckResult(qualname, False, repr(exc), True))
            continue
        if view._checks:
            results.extend(view._checks)
        else:
            results.append(CheckResult(qualname, True, "", True))
    return tuple(results)


# Teardown hooks run while the target is still up (before unwind) and one failing does not stop the others:
# evidence collection must survive a broken test run.
def run_teardown_hooks(registry, view: SessionView) -> tuple[tuple[str, bool, str], ...]:
    results: list[tuple[str, bool, str]] = []
    for hi in registry.pm.hook.itf_teardown.get_hookimpls():
        qualname = f"{hi.plugin.__name__}.{hi.function.__name__}"
        try:
            hi.function(view)
            results.append((qualname, True, ""))
        except Exception as exc:
            results.append((qualname, False, repr(exc)))
    return tuple(results)


@dataclass(frozen=True)
class UnwindReport:
    kept: bool
    probed: tuple[str, ...]
    dismantled: tuple[str, ...]
    errors: tuple[tuple[str, str], ...]


def unwind(
    target_plan, action_plan, realization, catalog, *, on_exit: str = "unwind", resolver=default_resolver, observer=None
) -> UnwindReport:
    if on_exit == "keep":
        return UnwindReport(kept=True, probed=(), dismantled=(), errors=())

    # Unwind only touches what was actually constructed, in reverse construction order. The probe pass is
    # for the report (what still held at exit), not a precondition: teardown never skips a node.
    observation = observe(action_plan, realization, resolver=resolver, observer=observer)
    dismantled: list[str] = []
    errors: list[tuple[str, str]] = []
    for ref in reversed(realization.construction_order):
        instance = realization.peek(ref)
        if instance is None:
            continue
        finish = realization.finalizer(ref)
        if finish is None:
            continue
        try:
            finish()
            dismantled.append(ref)
        except Exception as exc:
            errors.append((ref, repr(exc)))
    return UnwindReport(
        kept=False,
        probed=tuple(sorted(observation.holds)),
        dismantled=tuple(dismantled),
        errors=tuple(errors),
    )
