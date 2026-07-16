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


def test_ping_from_host_to_target(target):
    assert target.ping(timeout=10)


def test_ping_from_target_to_host(target):
    cmd = """
        gw=$(ip route | awk '/default/ {print $3; exit}')
        if [ -z \"$gw\" ]; then
            echo \"No default gateway found\" >&2
            exit 1
        fi
        ping -c 1 -W 5 \"$gw\"
    """
    exit_code, _ = target.execute(cmd)
    assert exit_code == 0
