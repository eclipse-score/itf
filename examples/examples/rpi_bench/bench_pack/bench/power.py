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
"""The bench power supply that powers the board.

Wire `BenchPowerSupply` to your instrument: SCPI over LAN or USB (pyvisa), a USB relay board, a smart PDU.
The contract `bench/power.supply` is the bench's own: tests and actions write a Protocol of the members they
use, and ITF checks that this class has them."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PowerSupplyConfig:
    address: str  # the instrument's address, e.g. "TCPIP::192.168.1.50::INSTR"
    channel: int = 1
    voltage: float = 5.1  # the Raspberry Pi's 5 V rail, with headroom for the cable
    current_limit: float = 3.0


class BenchPowerSupply:
    """One output channel of a bench power supply."""

    def __init__(self, config: dict):
        self.address = config["address"]
        self.channel = config.get("channel", 1)
        self.voltage = config.get("voltage", 5.1)
        self.current_limit = config.get("current_limit", 3.0)

    def on(self) -> None:
        """Set voltage and current limit, then switch the output on. Switching an output that is on does
        nothing."""
        raise NotImplementedError(f"switch on channel {self.channel} of {self.address}")

    def off(self) -> None:
        """Switch the output off. Switching an output that is off does nothing."""
        raise NotImplementedError(f"switch off channel {self.channel} of {self.address}")

    def is_on(self) -> bool:
        """The output state read back from the instrument, not remembered here."""
        raise NotImplementedError(f"read the output state of channel {self.channel} of {self.address}")

    def current(self) -> float:
        """The measured current in amperes: evidence that the board draws power, and a test of its own."""
        raise NotImplementedError(f"measure the current of channel {self.channel} of {self.address}")

    def close(self) -> None:
        """Release the instrument connection. The output keeps its state: the board's teardown switches it
        off."""
