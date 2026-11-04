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
"""Relation: how one kind of contract is resolved. The extension point of OCTO.

A `Kind` (kinds.py) is data. A `Relation` is the algorithm a kind's `ref` names, plus everything
OCTO needs to hold it to the core's guarantees: which claim types it owns (admission), which
diagnostic codes it may emit (the closed set), which edge reasons its plans use, and which earlier
relation's plan it consumes. `Octo` checks the declarations; tests/kinds checks the behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Relation:
    ref: str
    claim_types: tuple[type, ...]
    # (kind, claims, [upstream plan,] **options) -> (plan | None, diagnostics). Pure: no I/O, no clock,
    # no randomness, every collection iterated sorted.
    resolve: Callable
    codes: frozenset[str] = frozenset()
    edge_reasons: frozenset[str] = frozenset()
    upstream: str | None = None  # ref of the relation whose plan `resolve` receives
