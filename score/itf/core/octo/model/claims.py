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
"""Claims: the only input OCTO accepts. Frozen, hashable, no live objects.

The claim types themselves belong to the relation that resolves them (`Relation.claim_types`);
this module holds only what every claim shares: payload types and the canonical JSON envelope.
A claim may define `subject() -> str`, the name diagnostics about it use; otherwise its type name is.
"""

from __future__ import annotations

from typing import Iterable, Union

Scalar = Union[str, int, float, bool]
Pairs = tuple  # tuple[tuple[str, X], ...], always sorted by key


def subject_of(claim) -> str:
    subject = getattr(claim, "subject", None)
    return subject() if callable(subject) else type(claim).__name__


# `_kind` on the wire is the class name; used by canonical claim JSON and by `claims.json`.
def claim_to_json(claim) -> dict:
    data = claim.to_json()
    data["_kind"] = type(claim).__name__
    return data


def claim_from_json(data: dict, types: Iterable[type]):
    by_kind = {t.__name__: t for t in types}
    data = dict(data)
    return by_kind[data.pop("_kind")].from_json(data)


def claims_to_json(claims) -> list:
    return [claim_to_json(c) for c in sorted(claims, key=repr)]


def claims_from_json(data, types: Iterable[type]) -> frozenset:
    types = tuple(types)
    return frozenset(claim_from_json(d, types) for d in data)
