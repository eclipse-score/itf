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
"""Conformance of acme/power.relay: what a factory must do to honour it. Each check takes the offered object and
raises AssertionError through `expect`, so any runner can execute it; `itf contracts check` and ITF's
conformance plugin run them against every part that claims the contract."""

from score.itf.contracts.conformance import check, expect

RELAY = "acme/power.relay"


@check()
def a_relay_starts_open(node):
    expect(node.is_on() is False, "a relay must start open (off); is_on() said it is on")


@check()
def on_closes_the_relay_and_off_opens_it(node):
    node.on()
    expect(node.is_on() is True, "after on() returns, is_on() must be true")
    node.off()
    expect(node.is_on() is False, "after off() returns, is_on() must be false")


@check()
def switching_to_the_state_it_is_in_does_nothing(node):
    node.off()
    node.off()
    expect(node.is_on() is False, "off() on an open relay must leave it open")
    node.on()
    node.on()
    expect(node.is_on() is True, "on() on a closed relay must leave it closed")
    node.off()


@check(shape=("toggle",))
def toggle_flips_and_returns_the_new_state(node):
    node.off()
    expect(node.toggle() is True, "toggle() on an open relay must return True")
    expect(node.is_on() is True, "toggle() must leave the relay in the state it returned")
    expect(node.toggle() is False, "toggle() on a closed relay must return False")


CHECKS = {
    RELAY: [
        a_relay_starts_open,
        on_closes_the_relay_and_off_opens_it,
        switching_to_the_state_it_is_in_does_nothing,
        toggle_flips_and_returns_the_new_state,
    ]
}
