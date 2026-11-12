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
"""A suite that requires the vendor's contract and a contract nobody defined.

Consumer Protocols declare only the calls each test needs and pin the contract's major.
Power and LED tests have no common role requirement, so their requirements stay on the functions."""

from typing import Protocol

import score.itf as itf


class Relay(Protocol):
    __contract__ = "acme/power.relay@1"

    def on(self) -> None: ...
    def off(self) -> None: ...
    def is_on(self) -> bool: ...


class ToggleRelay(Protocol):
    __contract__ = "acme/power.relay@1"

    def off(self) -> None: ...
    def toggle(self) -> bool: ...


class Led(Protocol):
    __contract__ = "bench/led"

    def light(self, on: bool, /) -> None: ...
    def lit(self) -> bool: ...


@itf.requires("power", shape=Relay)
def test_the_relay_switches(target):
    target.power.off()
    assert not target.power.is_on()
    target.power.on()
    assert target.power.is_on()
    target.power.off()


@itf.requires("power", shape=ToggleRelay)
def test_the_optional_toggle(target):
    target.power.off()
    assert target.power.toggle() is True
    target.power.off()


@itf.requires("led", shape=Led)
def test_a_contract_without_a_definition(target):
    target.led.light(True)
    assert target.led.lit()
    target.led.light(False)
