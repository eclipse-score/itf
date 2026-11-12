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
"""Precedence-based override resolution, shared by node identity (Gate 1) and state
contract identity (Gate 2) — "everything arrives through one interface" for both."""

from __future__ import annotations

import dataclasses


def rank(origin: str, precedence: tuple[str, ...]) -> int:
    """Origins listed lowest first; an origin not listed ranks below all listed."""
    if origin in precedence:
        return precedence.index(origin) + 1
    return 0


def sort_key(claim) -> str:
    """Stable order independent of input iteration order when origins tie."""
    return repr(claim)


def content_key(claim) -> str:
    """Claim identity ignoring `origin`, for conflict comparison."""
    return repr(dataclasses.replace(claim, origin=""))


def resolve_group(group: list, precedence: tuple[str, ...]) -> tuple[object, bool]:
    """group: non-empty claims sharing one identity. Returns (winner, conflicting).

    The winner maximises rank(origin): r* = max over the group of rank(c.origin), winner in {c : rank = r*}.
    Several claims at r* are a conflict only when their contents differ (ignoring the origin); identical
    repeats are the same statement made twice. The tie is broken by `sort_key` so the winner never depends
    on input order, but a real conflict is still reported: the caller must not act on an arbitrary pick.
    """
    if len(group) == 1:
        return group[0], False
    best_rank = max(rank(c.origin, precedence) for c in group)
    top = [c for c in group if rank(c.origin, precedence) == best_rank]
    winner = sorted(top, key=sort_key)[0]
    if len(top) == 1:
        return winner, False
    contents = {content_key(c) for c in top}
    return winner, len(contents) > 1
