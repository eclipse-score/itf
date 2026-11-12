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
"""A capability, an action and its probe that record every call: what planning must never trigger."""

from typing import Protocol

from score.itf.core import capability, state

CALLS: list[str] = []
HOLDS = [False]  # what the probe answers


class Thing:
    def ping(self):
        return "pong"


class ThingContract(Protocol):
    __contract__ = "rec.thing"

    def ping(self): ...


@capability("rec.thing", label="thing")
def make_thing() -> Thing:
    CALLS.append("construct")
    return Thing()


@state("rec.ready", label="make_ready")
def make_ready(thing: ThingContract) -> None:
    CALLS.append("run")
    HOLDS[0] = True  # the state holds once the action ran


@make_ready.probe
def ready_probe(thing: ThingContract) -> bool:
    CALLS.append("probe")
    return HOLDS[0]
