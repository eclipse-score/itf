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
"""Kind descriptors: data, never code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["needs", "produces", "destroys", "uses"]


@dataclass(frozen=True)
class Kind:
    name: str
    ref: str  # names the Relation that resolves this kind
    roles: frozenset[str]
    idempotent: bool
    permanent: bool
    reversible: bool
    realization: Literal["construct", "invoke"]
    evidence: Literal["none", "shape", "probe"]
    scoped: bool
    identity: Literal["scope-name", "token"]
