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
"""What a run did, for the log, the run artifacts and the evidence record.

Nothing in the session decides anything from this record; it only reports. Fields are replaced, never mutated in
place: the artifact writer skips a file whose inputs are the very same objects as last time.
"""

from __future__ import annotations

import dataclasses
import time

from ..engine.failure import Failure
from ..engine.log import log_drift, log_event, log_plan_warnings
from ..engine.secrets import Secrets

# The events kept for the evidence record; every event is still logged.
_RECORDED = frozenset({"state_probed", "action_started", "action_finished", "action_skipped"})


class RunRecord:
    """The facts of one run. `secrets` masks every text ITF shows from it."""

    def __init__(self, secrets: Secrets):
        self.secrets = secrets
        # planning
        self.resolution_failure = None  # ResolutionFailed, when a gate failed
        self.config_issues: tuple = ()  # ((ref, provider, message), ...) from the settings check
        self.warnings: tuple[str, ...] = ()
        self.gating_decisions: tuple = ()  # ((test id, GatingDecision), ...) of the last select()
        self.preflight_report = None
        # bring-up and later
        self.brought_up = False  # bring-up started
        self.ready = False  # bring-up and the essential startup checks passed
        self.attempt: int | None = None  # the bring-up attempt running, which tags its events
        self.retries: tuple = ()  # ({attempt, lost, error}, ...): attempts that lost a state and planned again
        self.pre_observation = None  # what held before bring-up ran anything
        self.run_report = None  # the last executed plan's report
        self.check_results: tuple = ()  # startup checks (itf_verify)
        self.failure_text = ""  # the failure report shown when bring-up or a check failed
        self.events: tuple = ()  # ({phase, kind, t, ...}, ...): probes and actions, for the evidence
        self.probe_stats: dict = {}  # phase -> {count, ms, runs}
        self.drift: tuple = ()  # ({phase, dropped, appeared}, ...)
        # closing
        self.teardown_results: tuple = ()  # ((name, ok, error), ...) of itf_teardown
        self.unwind_report = None
        self.leaked_processes: tuple[str, ...] = ()

    def log_event(self, kind: str, data: dict) -> None:
        log_event(kind, self.secrets.mask_text_fields(data))

    def meter(self, forward=None):
        """An observer that counts probe calls and their time, keeps the recorded events, and forwards every
        event to `forward`."""
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

    def record_probes(self, phase: str, meter) -> None:
        """Keep what `meter` saw under `phase` (tagged with the bring-up attempt, if one runs)."""
        attempt = {"attempt": self.attempt} if self.attempt is not None else {}
        self.events = self.events + tuple({"phase": phase, **attempt, **e} for e in meter.events)
        meter.events.clear()
        prev = self.probe_stats.get(phase, {"count": 0, "ms": 0.0, "runs": 0})
        self.probe_stats = {
            **self.probe_stats,
            phase: {
                "count": prev["count"] + meter.counts["count"],
                "ms": round(prev["ms"] + meter.counts["ms"], 3),
                "runs": prev["runs"] + 1,
            },
        }

    def add_drift(self, phase: str, dropped: list, appeared: list) -> None:
        entry = {"phase": phase, "dropped": dropped, "appeared": appeared}
        self.drift = self.drift + (entry,)
        log_drift(entry)

    def add_retry(self, attempt: int, lost: list, error: str) -> None:
        self.retries = self.retries + ({"attempt": attempt, "lost": lost, "error": error},)

    def warn(self, messages) -> None:
        fresh = [m for m in messages if m not in self.warnings]
        if fresh:
            self.warnings = self.warnings + tuple(fresh)
            log_plan_warnings(fresh)

    def safe_failure(self, failure: Failure) -> Failure:
        """`failure` with every known secret masked."""
        return dataclasses.replace(
            failure,
            rows=tuple((label, self.secrets.mask(value)) for label, value in failure.rows),
            hints=tuple(self.secrets.mask(hint) for hint in failure.hints),
        )
