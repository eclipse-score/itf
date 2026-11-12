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
"""Runner-agnostic conformance checks: what a provider must do to honour a contract.

A conformance module (named by a definition's `conformance:`) defines `CHECKS: dict[str, list[Check]]` keyed by contract name. A check is a named
function `(node) -> None` that raises `AssertionError` with a readable message, so any runner (pytest,
a script, `itf` itself) can execute it; no module here imports a test framework. A check may raise
`Skip` when the situation it needs is absent (a tool missing on the target).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass


class Skip(Exception):
    """The role cannot take part in this check (not a failure)."""


@dataclass(frozen=True)
class Check:
    name: str
    run: Callable[[object], None]
    # Members the node must offer for the check to apply (optional members of a contract).
    shape: tuple[str, ...] = ()
    # Changes the node's state (restart): runners execute these last and re-reach the goals afterwards.
    disruptive: bool = False

    def __call__(self, node) -> None:
        self.run(node)


def check(*, shape: tuple[str, ...] = (), disruptive: bool = False, name: str | None = None):
    """Decorator turning `def some_check(node)` into a `Check` named after the function (or `name`)."""

    def wrap(func) -> Check:
        return Check(name or func.__name__, func, tuple(shape), disruptive)

    return wrap


def expect(condition: object, message: str) -> None:
    """`assert` that survives `python -O`, with a message naming what the contract promised."""
    if not condition:
        raise AssertionError(message)


def all_checks(definitions=None, *, contracts=None) -> dict[str, list[Check]]:
    """The checks of every definition that names a `conformance` module, keyed by contract name. Definitions
    come from `score.itf.contracts.load()` unless given. `contracts` restricts both module imports and
    returned checks to those contract names; unrelated providers need not be installed."""
    if definitions is None:
        from .. import load

        definitions = load()
    merged: dict[str, list[Check]] = {}
    selected = None if contracts is None else frozenset(contracts)
    seen = set()
    for definition in definitions.values():
        if selected is not None and definition.contract not in selected:
            continue
        if not definition.conformance or definition.conformance in seen:
            continue
        seen.add(definition.conformance)
        module = importlib.import_module(definition.conformance)
        for name, checks in module.CHECKS.items():
            if selected is None or name in selected:
                merged.setdefault(name, []).extend(checks)
    return merged


__all__ = ["Check", "Skip", "all_checks", "check", "expect"]
