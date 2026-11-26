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
"""Tests for the Raspberry Pi bench. Each test asks for the roles it uses, with a Protocol of the members it
calls, so the same file runs on any target that has those roles (a Pi on the bench, a QEMU machine with SSH)
and lists the rest as deselected."""

import re
import time
from contextlib import AbstractContextManager
from typing import Protocol

import score.itf as itf


class Power(Protocol):
    __contract__ = "bench/power.supply@1"

    def is_on(self) -> bool: ...
    def current(self) -> float: ...


class Restart(Protocol):
    __contract__ = "platform.instance"

    def restart(self) -> None: ...
    def running(self) -> bool: ...


class PowerCycle(Protocol):
    __contract__ = "platform.instance"

    def power_cycle(self) -> None: ...


class Ping(Protocol):
    __contract__ = "net.ping"

    def ping(self) -> bool: ...


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


class Files(Protocol):
    __contract__ = "files.transfer"

    def upload(self, local_path: str, remote_path: str) -> None: ...
    def download(self, remote_path: str, local_path: str) -> None: ...


class Logs(Protocol):
    __contract__ = "observe.logs"

    def window(self) -> AbstractContextManager: ...


class LogsOnTarget(Protocol):
    __contract__ = "logs.on_target"

    def start(self, transport: object) -> AbstractContextManager: ...


def send_dlt(target, message: str) -> None:
    code, output = target.command.exec(f"echo -n '{message}' | dlt-adaptor-stdin")
    assert code == 0, output


@itf.requires("power", shape=Power)
def test_the_board_is_powered_and_draws_current(target):
    assert target.power.is_on()
    assert target.power.current() > 0.1  # a Raspberry Pi idles well above 100 mA


@itf.requires("ping", shape=Ping)
def test_the_board_answers_ping(target):
    assert target.ping.ping()


@itf.requires("command", shape=Command)
def test_the_board_runs_commands_over_ssh(target):
    code, output = target.command.exec("uname -m")
    assert code == 0
    assert output.strip() == b"aarch64"


@itf.requires("files", shape=Files)
def test_a_file_survives_the_round_trip_over_sftp(target, tmp_path):
    sent, received = tmp_path / "sent.txt", tmp_path / "received.txt"
    sent.write_text("hello from the bench\n", encoding="utf-8")
    target.files.upload(str(sent), "/tmp/itf-bench.txt")
    target.files.download("/tmp/itf-bench.txt", str(received))
    assert received.read_text(encoding="utf-8") == sent.read_text(encoding="utf-8")


@itf.requires("logs", shape=Logs)
@itf.requires("command", shape=Command)
def test_dlt_sent_by_the_board_reaches_the_bench_host(target):
    with target.logs.window() as window:
        send_dlt(target, "itf-bench-external")
        time.sleep(1)
    assert window.record().find(query={"payload_decoded": re.compile("itf-bench-external")})


@itf.requires("dlt_on_target", shape=LogsOnTarget)
@itf.requires("command", shape=Command)
def test_the_boards_own_dlt_daemon_is_recorded_on_the_board(target):
    with target.dlt_on_target.start("tcp") as receiver:
        send_dlt(target, "itf-bench-internal")
        time.sleep(1)
    code, _ = target.command.exec(f"test -s {receiver.dlt_file}")
    assert code == 0, f"{receiver.dlt_file} is empty"


@itf.requires("platform", shape=Restart)
@itf.requires("command", shape=Command)
def test_the_board_comes_back_after_a_reboot(target):
    target.platform.restart()
    target.reach()  # the SSH session dropped with the reboot: every goal is planned again from the probes
    assert target.platform.running()
    assert target.command.exec("true")[0] == 0


@itf.requires("platform", shape=PowerCycle)
@itf.requires("command", shape=Command)
def test_the_board_comes_back_after_a_power_cycle(target):
    target.platform.power_cycle()
    target.reach()
    assert target.command.exec("true")[0] == 0
