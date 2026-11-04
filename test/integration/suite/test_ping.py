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
"""Any target the host can ping (`ping`)."""

import score.itf as itf


@itf.requires("ping")
def test_the_host_pings_the_target(target):
    assert target.ping.ping()


@itf.requires("command")
@itf.requires("ping")
def test_the_target_pings_its_gateway(target):
    code, output = target.command.exec(
        'gw=$(ip route | awk \'/default/ {print $3; exit}\'); [ -n "$gw" ] && ping -c 1 -W 5 "$gw"'
    )
    assert code == 0, output
