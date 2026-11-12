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
"""Conformance of the net area."""

from score.itf.contracts.conformance import check, expect

PING = "net.ping"


@check()
def host_is_a_nonempty_string(node):
    expect(isinstance(node.host, str) and node.host, f"host is {node.host!r}, expected a non-empty string")


@check()
def ping_returns_a_boolean(node):
    answer = node.ping()
    expect(isinstance(answer, bool), f"ping() returned {answer!r}, expected True or False")


CHECKS = {PING: [host_is_a_nonempty_string, ping_returns_a_boolean]}
