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
"""The bench's capability factories. Constructing one opens nothing on the board: the actions in steps.py do."""

from collections.abc import Iterator

from score.itf.core import capability

from .board import BoardConfig, Command, Pinger, PowerSupply, RaspberryPi
from .flasher import FlasherConfig, SdMuxFlasher
from .power import BenchPowerSupply, PowerSupplyConfig


@capability("bench/power.supply@1", label="power_supply")
def make_power_supply(config: PowerSupplyConfig) -> Iterator[BenchPowerSupply]:
    supply = BenchPowerSupply(config)
    try:
        yield supply
    finally:
        supply.close()


@capability("bench/image.flasher@1", label="sd_flasher")
def make_sd_flasher(config: FlasherConfig) -> SdMuxFlasher:
    return SdMuxFlasher(config)


@capability("platform.instance", label="raspberry_pi")
def make_raspberry_pi(power: PowerSupply, ping: Pinger, command: Command, config: BoardConfig) -> Iterator[RaspberryPi]:
    board = RaspberryPi(power, ping, command, config)
    try:
        yield board
    finally:
        board.stop()  # the end of the run powers the board off
