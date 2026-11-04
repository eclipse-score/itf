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
"""Lazy realization: nothing is constructed until fetched."""

from __future__ import annotations

import importlib
import inspect
from typing import Callable

from ..process import ProcessWrapper


class RealizationError(Exception):
    """A factory raised, or an `impl` reference could not be resolved."""


def _finalizer(ref: str, generator) -> Callable[[], None]:
    def finish() -> None:
        try:
            next(generator)
        except StopIteration:
            return
        raise RealizationError(f"the capability factory of {ref} yielded more than once")

    return finish


def default_resolver(impl: str) -> Callable:
    module_name, _, qualname = impl.partition(":")
    obj = importlib.import_module(module_name)
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


# Nodes are built on first use, in dependency order, never up front: a test that needs only a command
# does not pay for (or fail on) a console it never touches, and gating decides on the plan alone.
class Realization:
    def __init__(self, plan, *, owner=None, resolver: Callable[[str], Callable] = default_resolver):
        self._plan = plan
        self._owner = owner  # whose host processes the factories start (see ProcessWrapper.owned_by)
        self._resolver = resolver
        self._instances: dict[str, object] = {}
        self._finalizers: dict[str, Callable[[], None]] = {}
        self._order: list[str] = []

    def plan(self):
        return self._plan

    def tokens(self) -> tuple[str, ...]:
        return tuple(sorted({n.contract for n in self._plan.nodes}))

    def has(self, ref: str) -> bool:
        try:
            self._plan.resolve(ref)
        except KeyError:
            return False
        return True

    @property
    def construction_order(self) -> tuple[str, ...]:
        return tuple(self._order)

    def peek(self, ref: str):
        """The instance if already realized, else None. Never constructs."""
        try:
            real = self._plan.resolve(ref)
        except KeyError:
            return None
        return self._instances.get(real)

    def get(self, ref: str):
        real = self._plan.resolve(ref)
        if real in self._instances:
            return self._instances[real]
        node = self._plan.node(real)
        kwargs = {slot: self.get(bound_ref) for slot, bound_ref in node.bindings}
        factory = self._resolver(node.impl)
        params = inspect.signature(factory).parameters
        if "config" in params:
            kwargs["config"] = dict(node.config)
        try:
            # A provider that yields owns its teardown: code after the yield runs when the node is
            # dismantled (unwind or renew), so setup and cleanup stay in one place.
            with ProcessWrapper.owned_by(self._owner):
                if inspect.isgeneratorfunction(factory):
                    generator = factory(**kwargs)
                    instance = next(generator)
                    self._finalizers[real] = _finalizer(real, generator)
                else:
                    instance = factory(**kwargs)
        except Exception as exc:
            raise RealizationError(f"constructing {real}: {exc}") from exc
        self._instances[real] = instance
        self._order.append(real)
        return instance

    def finalizer(self, ref: str) -> Callable[[], None] | None:
        """Runs the rest of a yielding capability factory (its teardown), or None if it returned instead."""
        return self._finalizers.get(self._plan.resolve(ref))

    def discard(self, refs) -> tuple[str, ...]:
        """Dismantle `refs` and every realized node bound to one of them, newest first; the next
        `get` constructs them anew. Returns the dismantled refs; a failing teardown does not stop
        the others and is raised afterwards."""
        # Renewing a node also dismantles everything bound to it: a shell holding a dead container
        # connection is worse than a shell rebuilt against the new one.
        doomed = {self._plan.resolve(ref) for ref in refs}
        grew = True
        while grew:
            grew = False
            for real in self._order:
                if real not in doomed and any(
                    self._plan.resolve(bound) in doomed for _, bound in self._plan.node(real).bindings
                ):
                    doomed.add(real)
                    grew = True
        dismantled: list[str] = []
        errors: list[str] = []
        for real in reversed(self._order):
            if real not in doomed:
                continue
            finish = self._finalizers.pop(real, None)
            self._instances.pop(real)
            dismantled.append(real)
            if finish is not None:
                try:
                    finish()
                except Exception as exc:
                    errors.append(f"{real}: {exc!r}")
        self._order = [real for real in self._order if real not in doomed]
        if errors:
            raise RealizationError(f"dismantling {', '.join(errors)}")
        return tuple(dismantled)

    def resolve_all(self, extra_impls: tuple[str, ...] = ()) -> None:
        """Dry-run check: resolve every `impl` (roles, plus any extra refs), construct nothing."""
        for node in self._plan.nodes:
            self._resolver(node.impl)
        for impl in extra_impls:
            if impl:
                self._resolver(impl)
