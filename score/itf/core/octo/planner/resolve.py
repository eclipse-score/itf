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
"""`Octo`: one planner per kind set.

`Octo(kinds, relations).resolve(kind, claims, upstream=...)` is the only entry point. It knows no
kind: it admits claims by the relation that owns their type, runs that relation, and holds the
result to the core's guarantees — sorted diagnostics from the closed set, failures reported as
diagnostics rather than raised, and the kind set recorded in the plan.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable

from ..model.claims import subject_of
from ..model.diagnostics import CORE_CODES, Diagnostic
from ..model.kinds import Kind
from ..model.plans import Resolution
from ..model.relations import Relation


class KindSetInvalid(ValueError):
    """The kinds or relations an `Octo` was built with are inconsistent; a configuration defect."""


class Octo:
    def __init__(self, kinds: Iterable[Kind], relations: Iterable[Relation]):
        kinds, relations = tuple(kinds), tuple(relations)
        by_ref = {r.ref: r for r in relations}
        if len(by_ref) != len(relations):
            raise KindSetInvalid(f"two relations share a ref: {[r.ref for r in relations]}")
        if not kinds:
            raise KindSetInvalid("an Octo needs at least one kind")
        names = [k.name for k in kinds]
        if len(set(names)) != len(names):
            raise KindSetInvalid(f"kind names must be unique: {names}")
        refs = [k.ref for k in kinds]
        if len(set(refs)) != len(refs):
            raise KindSetInvalid(f"two kinds share a claim vocabulary (ref): {refs}")
        owners: dict[type, str] = {}
        for relation in relations:
            for t in relation.claim_types:
                if t in owners:
                    raise KindSetInvalid(f"claim type {t.__name__} owned by both {owners[t]!r} and {relation.ref!r}")
                owners[t] = relation.ref
        for i, k in enumerate(kinds):
            relation = by_ref.get(k.ref)
            if relation is None:
                raise KindSetInvalid(f"kind {k.name!r}: no relation for ref {k.ref!r}")
            if "uses" in k.roles and relation.upstream is None:
                raise KindSetInvalid(
                    f"kind {k.name!r} uses units of an earlier kind, but its relation names no upstream"
                )
            if relation.upstream is not None and relation.upstream not in refs[:i]:
                raise KindSetInvalid(
                    f"kind {k.name!r} uses units of an earlier kind ({relation.upstream!r}), and none precedes it"
                )
        self.kinds = kinds
        self._relations = {k.ref: by_ref[k.ref] for k in kinds}

    @property
    def codes(self) -> frozenset[str]:
        """The closed diagnostic set of this Octo: core codes plus every relation's."""
        return CORE_CODES.union(*(r.codes for r in self._relations.values()))

    def relation(self, kind: Kind) -> Relation:
        return self._relations[kind.ref]

    def gate(self, kind: Kind) -> int:
        if kind not in self.kinds:
            raise KindSetInvalid(f"kind {kind.name!r} is not registered with this Octo")
        return self.kinds.index(kind) + 1

    def resolve(self, kind: Kind, claims: Iterable, *, upstream=None, **options) -> Resolution:
        # Claims are admitted by type: a claim of another gate's vocabulary is a wrong-gate diagnostic,
        # not a silent skip, so a target file that mixes up "what must exist" and "what must happen" is told so.
        gate = self.gate(kind)
        relation = self._relations[kind.ref]
        others = tuple(t for k in self.kinds if k is not kind for t in self._relations[k.ref].claim_types)
        good, diags = [], []
        for c in claims:
            if isinstance(c, relation.claim_types):
                good.append(c)
            elif isinstance(c, others):
                diags.append(Diagnostic("CLAIM_WRONG_GATE", subject_of(c), gate))
            else:
                diags.append(Diagnostic("UNKNOWN_KIND", type(c).__name__, gate))

        args = (kind, good) if relation.upstream is None else (kind, good, upstream)
        # The planner never raises for a bad target file or a buggy relation: every failure becomes a diagnostic,
        # so `--itf-plan` can report all problems of a target file at once, before any hardware is touched.
        try:
            plan, more = relation.resolve(*args, **options)
        except Exception as exc:  # a relation's defect is reported like any other failure, never raised
            plan, more = (
                None,
                (Diagnostic("RELATION_FAILED", kind.name, gate, (("error", f"{type(exc).__name__}: {exc}"),)),),
            )
        # The diagnostic vocabulary is closed: a relation cannot invent codes, which keeps the catalog
        # and the docs able to list every message a user can ever see.
        allowed = CORE_CODES | relation.codes
        for d in more:
            if d.code in allowed:
                diags.append(dataclasses.replace(d, gate=gate))
            else:
                diags.append(Diagnostic("RELATION_FAILED", kind.name, gate, (("undeclared_code", d.code),)))
        # Sorted and de-duplicated: the same target file always yields byte-identical output (diffable plans).
        if diags or plan is None:
            return Resolution(None, tuple(sorted(set(diags), key=lambda d: (d.gate, d.code, d.subject, d.evidence))))
        return Resolution(dataclasses.replace(plan, kinds=tuple(k.name for k in self.kinds)), ())
