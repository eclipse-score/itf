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
"""Any target whose DLT logs the session receives (`logs`).
Messages are emitted with dlt-adaptor-stdin, which DLT targets ship."""

import re
import time
from contextlib import AbstractContextManager
from typing import Protocol as TypingProtocol

import score.itf as itf


class Message(TypingProtocol):
    def text(self) -> str: ...


class ActiveLogs(TypingProtocol):
    __contract__ = "observe.logs"

    def is_active(self) -> bool: ...


class StreamingLogs(TypingProtocol):
    __contract__ = "observe.logs"

    def lines(self) -> list[Message]: ...


class RecordingLogs(TypingProtocol):
    __contract__ = "observe.logs"

    def window(self) -> AbstractContextManager: ...


class OutputLogs(TypingProtocol):
    __contract__ = "observe.logs"

    def window(self, *, print_to_stdout: bool) -> AbstractContextManager: ...


class FilteredWindowLogs(TypingProtocol):
    __contract__ = "observe.logs"

    def window(self, *, dlt_filter: str, print_to_stdout: bool) -> AbstractContextManager: ...


class SelectedLogs(StreamingLogs, TypingProtocol):
    def filter(self, *, apid: str, ctid: str) -> list[Message]: ...


class MulticastWindowLogs(TypingProtocol):
    __contract__ = "observe.logs"

    def window(self, *, transport: object, host_ip: str, multicast_ips: list[str]) -> AbstractContextManager: ...


class Command(TypingProtocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


itf_requires = itf.requires("logs", contract="observe.logs")


def send(target, message: str) -> None:
    code, output = target.command.exec(f"echo -n '{message}' | dlt-adaptor-stdin")
    assert code == 0, output


def wait_for_text(logs, needle: str, timeout: float = 10.0) -> list:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if hits := [m for m in logs.lines() if needle in m.text()]:
            return hits
        time.sleep(0.3)
    return []


@itf.requires("logs", shape=ActiveLogs)
def test_a_log_stream_the_target_reached_is_active(target):
    assert target.logs.is_active() is True


@itf.requires("logs", shape=StreamingLogs)
@itf.requires("command", shape=Command)
def test_a_message_sent_on_the_target_is_received(target):
    send(target, "secret-session-message")
    assert wait_for_text(target.logs, "secret-session-message"), "message never arrived in the session logs"


@itf.requires("logs", shape=RecordingLogs)
@itf.requires("command", shape=Command)
def test_a_window_records_only_its_own_block_and_answers_queries(target):
    send(target, "before-window")
    with target.logs.window() as window:
        time.sleep(1)
        send(target, "inside-window")
        time.sleep(1)
    assert window.record().find(query={"payload_decoded": re.compile(r"inside-window")})
    assert all("before-window" not in m.text() for m in window.record().find())


@itf.requires("logs", shape=OutputLogs)
@itf.requires("command", shape=Command)
def test_a_window_logs_what_it_receives_only_when_asked_to(target):
    with target.logs.window(print_to_stdout=True) as loud:
        time.sleep(1)
        send(target, "loud-window")
        time.sleep(1)
        assert "loud-window" in loud.get_logged_output()  # a window keeps its output until its block ends
    with target.logs.window(print_to_stdout=False) as quiet:
        time.sleep(1)
        send(target, "quiet-window")
        time.sleep(1)
        assert len(quiet.get_logged_output()) == 0 and len(quiet.get_captured_logs()) == 0


@itf.requires("logs", shape=FilteredWindowLogs)
@itf.requires("command", shape=Command)
def test_a_window_filters_by_application_and_context(target):
    with target.logs.window(dlt_filter="SINA SINC", print_to_stdout=True) as window:  # dlt-adaptor-stdin's ids
        time.sleep(1)
        send(target, "filtered-window")
        time.sleep(1)
        assert "filtered-window" in window.get_logged_output()


@itf.requires("logs", shape=SelectedLogs)
@itf.requires("command", shape=Command)
def test_messages_can_be_selected_by_their_ids(target):
    send(target, "selected-by-ids")
    assert wait_for_text(target.logs, "selected-by-ids")
    assert any("selected-by-ids" in m.text() for m in target.logs.filter(apid="SINA", ctid="SINC"))
    assert target.logs.filter(apid="NONE", ctid="NONE") == []


@itf.requires("logs", shape=MulticastWindowLogs)
def test_a_window_can_listen_on_other_multicast_groups(target):
    from score.itf.packs.dlt.receive.process import Protocol  # only targets with the dlt pack get here

    groups = ["239.255.42.99", "231.255.42.99", "234.255.42.99", "237.255.42.99"]
    with target.logs.window(transport=Protocol.UDP, host_ip="127.0.0.1", multicast_ips=groups) as window:
        time.sleep(1)
        assert window.is_running()
