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
"""Conformance of the descriptor area: plain data."""

from score.itf.contracts.conformance import check, expect

ENDPOINT = "descriptor.endpoint"
CREDENTIALS = "descriptor.credentials"


@check()
def host_is_a_nonempty_string(node):
    expect(isinstance(node.host, str) and node.host, f"host is {node.host!r}, expected a non-empty string")


@check()
def port_is_a_valid_tcp_port(node):
    port = node.port
    expect(isinstance(port, int) and not isinstance(port, bool), f"port is {port!r}, expected an integer")
    expect(1 <= port <= 65535, f"port {port} is outside 1..65535")


@check()
def user_is_a_nonempty_string(node):
    expect(isinstance(node.user, str) and node.user, f"user is {node.user!r}, expected a non-empty string")


@check()
def a_secret_is_a_string_or_none(node):
    for name in ("password", "key_path"):
        value = getattr(node, name)
        expect(value is None or isinstance(value, str), f"{name} is {value!r}, expected a string or None")


CHECKS = {
    ENDPOINT: [host_is_a_nonempty_string, port_is_a_valid_tcp_port],
    CREDENTIALS: [user_is_a_nonempty_string, a_secret_is_a_string_or_none],
}
