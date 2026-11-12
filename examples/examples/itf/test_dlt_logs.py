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
"""DLT logs of the target, received by the session (`logs`)."""

import time
from typing import Protocol

import score.itf as itf


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


class StreamingLogs(Protocol):
    __contract__ = "observe.logs"

    def lines(self) -> list: ...


class FilteredLogs(Protocol):
    __contract__ = "observe.logs"

    def filter(self, *, apid: str) -> list: ...


itf_requires = [itf.requires("command", shape=Command), itf.requires("logs", shape=StreamingLogs)]


def wait_for_text(logs, needle: str, timeout: float = 10.0) -> list:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if hits := [m for m in logs.lines() if needle in m.text()]:
            return hits
        time.sleep(0.3)
    return []


def test_a_message_sent_on_the_target_reaches_the_session_logs(target):
    code, output = target.command.exec("echo -n 'hello from the app' | dlt-adaptor-stdin")
    assert code == 0, output
    assert wait_for_text(target.logs, "hello from the app"), "the message never arrived in the session logs"


@itf.requires("logs", shape=FilteredLogs)
def test_messages_can_be_filtered_by_application_id(target):
    target.command.exec("echo -n 'filter me' | dlt-adaptor-stdin")
    assert wait_for_text(target.logs, "filter me")
    assert target.logs.filter(apid="SINA") and not target.logs.filter(apid="NONE")
