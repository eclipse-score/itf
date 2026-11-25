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
"""Any target that starts processes asynchronously (`process`)."""

from typing import Protocol
from uuid import uuid4

import pytest

import score.itf as itf
from score.itf.core.process import WrappedProcess


class Spawn(Protocol):
    __contract__ = "exec.process"

    def spawn(self, binary_path: str, /) -> object: ...


class SpawnInDirectory(Protocol):
    __contract__ = "exec.process"

    def spawn(self, binary_path: str, /, *, cwd: str) -> object: ...


class SpawnWithArguments(Protocol):
    __contract__ = "exec.process"

    def spawn(self, binary_path: str, /, *, args: list[str]) -> object: ...


class SpawnWithArgumentsInDirectory(Protocol):
    __contract__ = "exec.process"

    def spawn(self, binary_path: str, /, *, args: list[str], cwd: str) -> object: ...


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


itf_requires = [itf.requires("process", shape=Spawn)]


@pytest.fixture
def target_scratch(target):
    directory = f"/tmp/itf-process-{uuid4().hex}"
    process = target.process.spawn(f"mkdir {directory}")
    assert process.wait(timeout_s=30) == 0
    try:
        yield directory
    finally:
        process = target.process.spawn(f"rm -rf {directory}")
        assert process.wait(timeout_s=30) == 0


def test_a_process_reports_pid_running_and_exit_code(target):
    process = target.process.spawn("sleep 1; exit 42")
    assert process.pid() > 0 and process.is_running()
    assert process.wait(timeout_s=30) == 42
    assert not process.is_running()


def test_stop_terminates_a_long_running_process(target):
    process = target.process.spawn("sleep 300")
    assert process.stop() in (143, 137)
    assert not process.is_running()


def test_output_is_captured(target):
    process = target.process.spawn("echo line1; echo line2; echo line3")
    process.wait(timeout_s=30)
    assert process.get_output().splitlines() == ["line1", "line2", "line3"]


@itf.requires("process", shape=SpawnInDirectory)
def test_cwd_is_honoured(target, target_scratch):
    process = target.process.spawn("pwd", cwd=target_scratch)
    assert process.wait(timeout_s=30) == 0 and process.get_output().strip() == target_scratch


@itf.requires("process", shape=SpawnWithArgumentsInDirectory)
def test_wrapped_processes_coordinate(target, target_scratch):
    marker = f"{target_scratch}/ready"
    waiter = f"while [ ! -f {marker} ]; do sleep 0.1; done; echo done"
    with WrappedProcess(target.process, waiter, wait_on_exit=True) as first:
        with WrappedProcess(target.process, f"sleep 0.5; touch {marker}", wait_on_exit=True):
            pass
    assert first.ret_code == 0 and "done" in first.get_output()


@itf.requires("process", shape=SpawnWithArgumentsInDirectory)
@itf.requires("command", shape=Command)
def test_arguments_reach_the_binary_one_by_one_spaces_included(target, target_scratch):
    process = target.process.spawn("touch", args=["hello world"], cwd=target_scratch)
    assert process.wait(timeout_s=30) == 0
    assert target.command.exec(f"ls '{target_scratch}/hello world'")[0] == 0, "an argument with a space was split"
    assert target.command.exec(f"test ! -e '{target_scratch}/hello' && test ! -e '{target_scratch}/world'")[0] == 0


@itf.requires("process", shape=SpawnWithArguments)
@itf.requires("command", shape=Command)
def test_an_absolute_binary_path_is_used_as_given(target):
    code, output = target.command.exec("which echo")
    path = output.decode().strip()
    assert code == 0 and path.startswith("/"), f"no absolute echo on the target: {path!r}"
    process = target.process.spawn(path, args=["absolute_ok"])
    assert process.wait(timeout_s=30) == 0 and "absolute_ok" in process.get_output()


@itf.requires("process", shape=SpawnWithArgumentsInDirectory)
def test_a_wrapped_process_is_stopped_when_its_block_ends(target):
    with WrappedProcess(target.process, "sleep 300") as wrapped:
        assert wrapped.is_running()
    assert not wrapped.is_running()


@itf.requires("process", shape=SpawnWithArgumentsInDirectory)
def test_a_wrapped_process_may_end_with_the_exit_code_it_expects(target):
    with WrappedProcess(
        target.process, "sh", args=["-c", "exit 42"], wait_on_exit=True, expected_exit_code=42
    ) as waited:
        pass
    assert waited.ret_code == 42
    with WrappedProcess(target.process, "sh", args=["-c", "exit 7"], expected_exit_code=7) as crashed:
        assert crashed.wait(timeout_s=30) == 7
    assert crashed.ret_code == 7
