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
"""The project's own code: a status LED that tests light while they run. Its contract, `bench/led`, has no
definition anywhere: the factory publishes its shape, the test expects members of it, and ITF checks the two
agree. Code outside a pack belongs to the pack `project`, so the label is `local.status_led`."""

from score.itf.core import capability


class StatusLed:
    """The operator LED of this target, simulated."""

    def __init__(self) -> None:
        self._lit = False

    def light(self, on: bool) -> None:
        self._lit = on

    def lit(self) -> bool:
        return self._lit


@capability("bench/led")
def status_led() -> StatusLed:
    return StatusLed()
