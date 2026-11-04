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
"""Diagnostics: a closed set of codes with structured evidence. No prose; the caller renders sentences.

The set is closed per `Octo`: the core codes below, plus the codes each registered relation declares.
"""

from __future__ import annotations

from dataclasses import dataclass

from .claims import Pairs
from .shapes import Shape, classify

CORE_CODES = frozenset(
    {
        "CLAIM_WRONG_GATE",
        "UNKNOWN_KIND",
        "RELATION_FAILED",
        "SHAPE_MISSING_MEMBER",
        "SHAPE_SIGNATURE_DRIFT",
        "SHAPE_PROTOCOL_MISSING",
        "SHAPE_UNDECLARED",
    }
)


# ---------------------------------------------------------------- diagnostics


@dataclass(frozen=True, order=True)
class Diagnostic:
    code: str  # member of the Octo's closed set
    subject: str
    gate: int  # 1-based position of the kind in its Octo
    evidence: Pairs = ()  # ((key, str), ...), sorted


def shape_mismatches(subject: str, given: Shape, expected: Shape, gate: int) -> list[Diagnostic]:
    """The seam check, wherever a consumer meets what it binds to. A consumer that expects nothing of what it
    binds to is itself an error (SHAPE_UNDECLARED): a slot says which members it relies on."""
    members, drift, protocols = classify(given, expected)
    out = []
    if members:
        out.append(Diagnostic("SHAPE_MISSING_MEMBER", subject, gate, tuple(("member", m) for m in members)))
    if drift:
        out.append(Diagnostic("SHAPE_SIGNATURE_DRIFT", subject, gate, tuple(("member", m) for m in drift)))
    if protocols:
        out.append(Diagnostic("SHAPE_PROTOCOL_MISSING", subject, gate, tuple(("protocol", p) for p in protocols)))
    if not expected.members and not expected.protocols:
        out.append(Diagnostic("SHAPE_UNDECLARED", subject, gate))
    return out
