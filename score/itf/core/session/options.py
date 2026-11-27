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
"""The options a session takes, and the values each may have."""

from __future__ import annotations

GATING = ("skip", "fail")
REUSE = ("probe", "fresh")
ON_EXIT = ("unwind", "keep")
# What a run leaves in its run directory: nothing, what a person reads (the default), or every file ITF writes.
ARTIFACTS = ("none", "standard", "full")
# A ${NAME} with no value: an error, or (planning only) a placeholder, for a compile that never builds.
UNSET = ("fail", "placeholder")


def one_of(name: str, value: str, allowed: tuple) -> str:
    if value not in allowed:
        raise ValueError(f"{name} is one of {', '.join(map(repr, allowed))}, not {value!r}")
    return value


def attempts(value) -> int:
    """How often bring-up may plan again when a step fails because a state that held stopped holding (a machine
    that died while booting); any other failure ends bring-up at once."""
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"bring_up_attempts must be a whole number from 1, not {value!r}")
    return value
