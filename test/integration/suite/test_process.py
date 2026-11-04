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

import time

import score.itf as itf
from score.itf.core.process import WrappedProcess


@itf.requires("process")
def test_a_process_reports_pid_running_and_exit_code(target):
    process = target.process.spawn("sleep 1; exit 42")
    assert process.pid() > 0 and process.is_running()
    assert process.wait(timeout_s=30) == 42
    assert not process.is_running()


@itf.requires("process")
def test_stop_terminates_a_long_running_process(target):
    process = target.process.spawn("sleep 300")
    assert process.stop() in (143, 137)
    assert not process.is_running()


@itf.requires("process")
def test_output_is_captured(target):
    process = target.process.spawn("echo first; echo second")
    process.wait(timeout_s=30)
    assert process.get_output().split() == ["first", "second"]


@itf.requires("process")
def test_cwd_is_honoured(target):
    process = target.process.spawn("pwd", cwd="/tmp")
    assert process.wait(timeout_s=30) == 0 and "/tmp" in process.get_output()


@itf.requires("process")
def test_wrapped_processes_coordinate(target):
    marker = "/tmp/itf_wrapped_ready"
    with WrappedProcess(target.process, f"rm -f {marker}", wait_on_exit=True):
        pass
    waiter = f"while [ ! -f {marker} ]; do sleep 0.1; done; echo done"
    with WrappedProcess(target.process, waiter, wait_on_exit=True) as first:
        with WrappedProcess(target.process, f"sleep 0.5; touch {marker}", wait_on_exit=True):
            pass
    assert first.ret_code == 0 and "done" in first.get_output()


@itf.requires("process")
@itf.requires("command")
def test_arguments_reach_the_binary_one_by_one_spaces_included(target):
    target.command.exec("rm -f '/tmp/hello world' /tmp/hello /tmp/world")
    process = target.process.spawn("touch", args=["hello world"], cwd="/tmp")
    assert process.wait(timeout_s=30) == 0
    assert target.command.exec("ls '/tmp/hello world'")[0] == 0, "an argument with a space was split"
    target.command.exec("rm -f '/tmp/hello world'")


@itf.requires("process")
@itf.requires("command")
def test_an_absolute_binary_path_is_used_as_given(target):
    code, output = target.command.exec("which echo")
    path = output.decode().strip()
    assert code == 0 and path.startswith("/"), f"no absolute echo on the target: {path!r}"
    process = target.process.spawn(path, args=["absolute_ok"])
    assert process.wait(timeout_s=30) == 0 and "absolute_ok" in process.get_output()


@itf.requires("process")
def test_a_wrapped_process_is_stopped_when_its_block_ends(target):
    with WrappedProcess(target.process, "sleep 300") as wrapped:
        assert wrapped.is_running()
    assert not wrapped.is_running()


@itf.requires("process")
def test_a_wrapped_process_may_end_with_the_exit_code_it_expects(target):
    with WrappedProcess(
        target.process, "sh", args=["-c", "exit 42"], wait_on_exit=True, expected_exit_code=42
    ) as waited:
        pass
    assert waited.ret_code == 42
    with WrappedProcess(target.process, "sh", args=["-c", "exit 7"], expected_exit_code=7) as crashed:
        time.sleep(2)  # it exits on its own before the block ends: its real exit code is kept
    assert crashed.ret_code == 7
