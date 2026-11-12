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
"""The simulated relay. A real factory drives a USB board or a network switch behind the same members; the
contract is what tests rely on, so they run unchanged on either."""

from score.itf.core import capability


class SimulatedRelay:
    """A relay held in memory. Starts open, as the contract guarantees."""

    def __init__(self) -> None:
        self._closed = False

    def on(self) -> None:
        self._closed = True

    def off(self) -> None:
        self._closed = False

    def is_on(self) -> bool:
        return self._closed

    def toggle(self) -> bool:
        self._closed = not self._closed
        return self._closed


@capability("acme/power.relay@1")  # label: acme.simulated_relay; the contract name is the vendor's own
def simulated_relay() -> SimulatedRelay:
    return SimulatedRelay()
