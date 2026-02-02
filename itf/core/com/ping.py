# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
import os
import time


def _execute_command(cmd):
    return os.system(cmd)


def _ping(address, wait_ms_precision=None):
    timeout_command = f"timeout {wait_ms_precision} " if wait_ms_precision else ""
    return _execute_command(f"{timeout_command}ping -c 1 -W 1 " + address) == 0


def ping(address, timeout=0, interval=1, wait_ms_precision=None):
    if timeout == 0:
        return _ping(address, wait_ms_precision)

    attempts = int(timeout / interval)

    for _ in range(attempts):
        time.sleep(interval)
        if _ping(address, wait_ms_precision):
            return True

    return False


def ping_lost(address, timeout=0, interval=1, wait_ms_precision=None):
    if timeout == 0:
        return not _ping(address, wait_ms_precision)

    attempts = int(timeout / interval)

    for _ in range(attempts):
        time.sleep(interval)
        if not _ping(address, wait_ms_precision):
            return True

    return False


def check_ping_lost(address):
    assert ping_lost(address, timeout=60)


def check_ping(address):
    assert ping(address, timeout=60)
