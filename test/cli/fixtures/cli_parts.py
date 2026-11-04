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
"""The project's own parts for the command line tests: two switches (one conforming), a panel that expects too
much, a dial a definition asks more of, and three actions that need ordering."""

from typing import Protocol

from score.itf.core import capability, state


class Switch:
    def __init__(self, on: bool):
        self._on = on

    def is_on(self) -> bool:
        return self._on


class WantsFlip(Protocol):
    __contract__ = "acme/toggle"

    def flip(self): ...


class Dial:
    def read(self) -> int:
        return 0


@capability("acme/toggle", label="good_switch")
def good() -> Switch:
    return Switch(False)


@capability("acme/toggle", label="bad_switch")
def bad() -> Switch:
    return Switch(True)


@capability("acme/panel", label="panel")
def panel(switch: WantsFlip) -> object:
    return object()


@capability("acme/dial", label="dial")
def dial() -> Dial:
    return Dial()


@state("acme/x", label="make_x")
def make_x() -> None: ...


@state("acme/y", label="make_y")
def make_y() -> None: ...


@make_y.probe
def y_holds() -> bool:
    return False


@state("acme/z", breaks=("acme/x",), label="make_z")
def make_z() -> None: ...
