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
"""Parts that agree and disagree on contract names, for the contract map."""

from typing import Protocol

from score.itf.core import capability, state


class Relay:
    def switch(self, on: bool): ...
    def read(self): ...


class WantsSwitch(Protocol):
    __contract__ = "acme/power.relay"

    def switch(self, on: bool): ...


class WantsToggle(Protocol):
    __contract__ = "acme/power.relay"

    def toggle(self): ...


class WantsSecondMajor(Protocol):
    __contract__ = "acme/power.relay@2"

    def switch(self, on: bool): ...


@capability("acme/power.relay@1", label="relay")
def make_relay() -> Relay: ...


@capability("acme/bench.rack", label="rack")
def make_rack(relay: WantsSwitch) -> object: ...


@capability("acme/bench.cabinet", label="cabinet")
def make_cabinet(relay: WantsToggle) -> object: ...


@capability("acme/bench.lab", label="lab")
def make_lab(relay: WantsSecondMajor) -> object: ...


@state("acme/power.on", after=("acme/power.ready",), label="power_on")
def power_on(relay: WantsSwitch) -> None: ...
