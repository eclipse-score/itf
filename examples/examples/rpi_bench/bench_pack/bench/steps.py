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
"""The bench's actions: flash the card, start the board. Each has a probe, so a run skips what already holds
(a card that holds the image is not written again)."""

from typing import Protocol

from score.itf.core import state


class PowerSupply(Protocol):
    __contract__ = "bench/power.supply"

    def off(self) -> None: ...


class Flasher(Protocol):
    __contract__ = "bench/image.flasher"

    def flash(self) -> None: ...
    def is_flashed(self) -> bool: ...


class Platform(Protocol):
    __contract__ = "platform.instance"

    def start(self) -> None: ...
    def running(self) -> bool: ...


# Writing the card needs the board off, so flashing ends `platform.up`: when a run flashes a board that is up,
# the planner starts it again afterwards.
@state("image.flashed", breaks=("platform.up",), label="flash")
def flash(flasher: Flasher, power: PowerSupply) -> None:
    power.off()
    flasher.flash()


@flash.probe
def is_flashed(flasher: Flasher, power: PowerSupply) -> bool:
    return flasher.is_flashed()


@state("platform.up", label="start")
def start(platform: Platform) -> None:
    platform.start()


@start.probe
def is_up(platform: Platform) -> bool:
    return platform.running()
