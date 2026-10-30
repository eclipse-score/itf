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
import http.client
import time

import pytest


@pytest.fixture
def slow_reply_reader(monkeypatch):
    """Emulate a loaded host: the client reads the reply of a request late.

    The daemon then sends the HTTP response headers and the first exec output in
    one burst, which http.client swallows into its read buffer.
    """
    original = http.client.HTTPConnection.getresponse

    def delayed_getresponse(self, *args, **kwargs):
        time.sleep(0.5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(http.client.HTTPConnection, "getresponse", delayed_getresponse)


def test_execute_returns_output_with_slow_reader(target, slow_reply_reader):
    exit_code, output = target.execute("echo Hello World!")
    assert exit_code == 0
    assert output.decode() == "Hello World!\n"


def test_execute_async_pid_not_lost_with_slow_reader(target, slow_reply_reader):
    proc = target.execute_async("sleep 0.3; echo first_application_log; sleep 5")
    try:
        assert proc.pid() > 0
        assert proc.is_running()
    finally:
        proc.stop()
