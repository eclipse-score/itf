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
"""Generic plan pieces every relation may use: a seam between a consumer and what it binds to, an
ordering edge with its reason, and the resolution wrapper `Octo.resolve` returns."""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import Diagnostic


@dataclass(frozen=True)
class Seam:
    consumer: str  # "scope.name" or "scope:state"
    slot: str
    provider: str  # node ref
    expected: tuple[str, ...]
    given: tuple[str, ...]


@dataclass(frozen=True)
class Edge:
    before: str  # step key
    after: str  # step key
    reason: str  # one of the producing relation's edge_reasons
    state: str  # "scope:token" the edge is about


@dataclass(frozen=True)
class Resolution:
    plan: object | None  # the relation's plan type, or None when diagnostics exist
    diagnostics: tuple[Diagnostic, ...] = ()

    def ok(self) -> bool:
        return self.plan is not None and not self.diagnostics
