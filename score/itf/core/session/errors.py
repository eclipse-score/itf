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
"""What a session raises."""

from __future__ import annotations

from ..engine.labels import node_label
from ..engine.scopes import display


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
