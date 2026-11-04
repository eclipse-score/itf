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
"""A machine that can die while it boots: powering it makes box.up true, but on the boots listed in PANIC_BOOTS it
dies before the link comes up, so linking fails and box.up stops holding. BROKEN_LINK makes linking fail with the machine up."""

from typing import Protocol

from score.itf.core import capability, state

PANIC_BOOTS: set[int] = set()
BROKEN_LINK: list[bool] = [False]


class Machine:
    def __init__(self):
        self.boots, self.alive, self.linked = 0, False, False

    def boot(self):
        self.boots += 1
        self.alive = True

    def settle(self):
        if self.boots in PANIC_BOOTS:  # a panic: up for an instant, then gone
            self.alive = False


class Box(Protocol):
    __contract__ = "box.machine"

    def boot(self): ...

    def settle(self): ...


@capability("box.machine", label="machine")
def make_machine() -> Machine:
    return Machine()


@state("box.up", label="power")
def power(machine: Box) -> None:
    machine.boot()


@power.probe
def powered(machine: Box) -> bool:
    return machine.alive


@state("box.linked", after=("box.up",), label="link")
def link(machine: Box) -> None:
    machine.settle()
    if not machine.alive:
        raise ConnectionError("no banner: the machine is gone")
    if BROKEN_LINK[0]:
        raise ConnectionError("the link refused, the machine is fine")
    machine.linked = True


@link.probe
def linked(machine: Box) -> bool:
    return machine.alive and machine.linked
