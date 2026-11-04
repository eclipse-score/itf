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
"""The target's unnamed root scope and the reference syntax around it.

Users never type ROOT: top-level keys of a target file are the root scope, `.name` names one of its roles and
`:token` one of its states. Scopes are named, and nothing falls back from one to the root.

`display` is the one place the engine's internal strings become what people read: the root scope is not
shown (`command`, `platform.up`, `gw.command`, `gw:platform.up`).
"""

from __future__ import annotations

import keyword
import re

ROOT = "__itf_root__"

# Public members of a scope view, and of the whole target; a node or scope name must not shadow them.
VIEW_MEMBERS = frozenset(
    {"scope", "tokens", "has", "names", "get", "states", "probe", "plan", "reach", "renew", "discard"}
)
TARGET_MEMBERS = VIEW_MEMBERS | {"scopes"}

_ROOT_QUALIFIER = re.compile(rf"(?<!\w){ROOT}[.:]")
_ROOT_BARE = re.compile(rf"(?<!\w){ROOT}\b")


class InvalidScopeName(ValueError):
    pass


def check_scope_name(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name.isidentifier()
        or keyword.iskeyword(name)
        or name.startswith("_")
        or name == "target"
        or name in TARGET_MEMBERS
    ):
        raise InvalidScopeName(
            f"scope name {name!r} must be a Python identifier, not a keyword, not 'target', not one of "
            f"{', '.join(sorted(TARGET_MEMBERS))}, and not start with '_' (it becomes target.{name})"
        )
    return name


def _check_ref(ref) -> str:
    if not isinstance(ref, str):
        raise TypeError(f"a reference must be a string, not {ref!r}")
    return ref


def node_ref(ref: str) -> str:
    """`.name` -> the root scope's node; anything else is passed through unchanged."""
    return f"{ROOT}{ref}" if _check_ref(ref).startswith(".") else ref


def state_ref(ref: str) -> str:
    """`:token` -> the root scope's state; anything else is passed through unchanged."""
    return f"{ROOT}{ref}" if _check_ref(ref).startswith(":") else ref


def display(text: str) -> str:
    """Render ROOT the way people read it: no root qualifier, `target` for the scope itself."""
    return _ROOT_BARE.sub("target", _ROOT_QUALIFIER.sub("", text))


def display_json(data):
    """`display` over a JSON-shaped value; `config` payloads are opaque and left untouched."""
    if isinstance(data, str):
        return display(data)
    if isinstance(data, dict):
        return {display(k): v if k == "config" else display_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [display_json(x) for x in data]
    return data
