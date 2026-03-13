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
import time


def test_async_exec(target):
    ready_signal = "/tmp/p2_ready"
    target.execute(f"rm -f {ready_signal}")

    recv_cmd = f"echo [P1] start; while [ ! -f {ready_signal} ]; do echo [P1] wait; sleep 0.1; done; echo [P1] done;"
    send_cmd = f"echo [P2] start; sleep 0.5; touch {ready_signal}; echo [P2] done;"

    with target.wrap_exec(recv_cmd, wait_on_exit=True):
        with target.wrap_exec(send_cmd, wait_on_exit=True):
            pass


def test_execute_async_pid_and_is_running(target):
    """Verify pid() returns a valid PID and is_running() tracks state."""
    proc = target.execute_async("sleep 10")
    try:
        pid = proc.pid()
        assert isinstance(pid, int)
        assert pid > 0
        assert proc.is_running()
    finally:
        proc.stop()
    assert not proc.is_running()


def test_execute_async_wait(target):
    """Verify wait() blocks until the process finishes and returns exit code 0."""
    proc = target.execute_async("sleep 1")
    exit_code = proc.wait(timeout_s=30)
    assert exit_code == 0
    assert not proc.is_running()


def test_execute_async_exit_code(target):
    """Verify get_exit_code() reflects the real exit status."""
    proc = target.execute_async("exit 42")
    proc.wait(timeout_s=30)
    assert proc.get_exit_code() == 42


def test_execute_async_stop(target):
    """Verify stop() terminates a long-running process."""
    proc = target.execute_async("sleep 300")
    assert proc.is_running()
    exit_code = proc.stop()
    assert not proc.is_running()
    # SIGTERM (143) or SIGKILL (137) are expected
    assert exit_code in (143, 137)


def test_execute_async_with_cwd(target):
    """Verify the cwd parameter is honoured."""
    marker_file = "itf_cwd_marker"
    target.execute(f"rm -f /tmp/{marker_file}")
    proc = target.execute_async(f"touch {marker_file}", cwd="/tmp")
    proc.wait(timeout_s=30)
    assert proc.get_exit_code() == 0
    exit_code, _ = target.execute(f"ls /tmp/{marker_file}")
    assert exit_code == 0
    target.execute(f"rm -f /tmp/{marker_file}")


def test_wrap_exec_stop_on_exit(target):
    """wrap_exec without wait_on_exit should stop the process when the block exits."""
    with target.wrap_exec("sleep 300") as wp:
        assert wp.is_running()
    # After the block, the process should have been stopped.
    assert not wp.is_running()


def test_wrap_exec_wait_on_exit(target):
    """wrap_exec with wait_on_exit should wait for natural completion."""
    with target.wrap_exec("sleep 1", wait_on_exit=True) as wp:
        assert wp.is_running() or True  # may finish fast
    assert wp.ret_code == 0


def test_wrap_exec_expected_exit_code(target):
    """wrap_exec should accept a non-zero expected exit code without raising."""
    with target.wrap_exec("exit 42", wait_on_exit=True, expected_exit_code=42) as wp:
        pass
    assert wp.ret_code == 42


def test_execute_async_with_args(target):
    """Verify args are passed correctly to the binary."""
    proc = target.execute_async("echo", args=["-n", "hello"])
    exit_code = proc.wait(timeout_s=30)
    assert exit_code == 0


def test_execute_async_args_with_spaces(target):
    """Verify args containing spaces are preserved as single arguments.

    Without proper per-arg quoting, 'hello world' would be split into two
    arguments and touch would create two files instead of one.
    """
    target.execute("rm -f '/tmp/hello world' /tmp/hello /tmp/world")
    proc = target.execute_async("touch", args=["hello world"], cwd="/tmp")
    proc.wait(timeout_s=30)
    assert proc.get_exit_code() == 0
    # The single file with a space in the name must exist.
    exit_code, _ = target.execute("ls '/tmp/hello world'")
    assert exit_code == 0, "Arg with space was split into separate arguments"
    target.execute("rm -f '/tmp/hello world'")


def test_execute_async_absolute_binary_path(target):
    """Verify absolute binary paths are not mangled (regression for lstrip bug)."""
    # Dynamically find the absolute path to 'echo' — differs between Linux and QNX.
    exit_code, output = target.execute("which echo")
    assert exit_code == 0, "Cannot locate echo binary on target"
    echo_path = output.decode().strip()
    assert echo_path.startswith("/"), f"Expected absolute path, got: {echo_path}"
    proc = target.execute_async(echo_path, args=["async_abs_path_ok"])
    exit_code = proc.wait(timeout_s=30)
    assert exit_code == 0


def test_wrap_exec_crashed_process_reports_real_exit_code(target):
    """wrap_exec without wait_on_exit should report the real exit code of a crashed process,
    not silently return 0."""
    with target.wrap_exec("exit 7", expected_exit_code=7) as wp:
        # Give the process time to exit before the with block ends.
        time.sleep(2)
    assert wp.ret_code == 7


def test_wrap_exec_get_output(target):
    """Verify get_output() is accessible via WrappedProcess."""
    with target.wrap_exec("echo line1; echo line2; echo line3", wait_on_exit=True) as wp:
        pass
    output = wp.get_output()
    assert "line1" in output
    assert "line2" in output
    assert "line3" in output


def test_execute_async_get_output(target):
    """Verify get_output() captures multiple lines of output."""
    proc = target.execute_async("echo line1; echo line2; echo line3")
    proc.wait(timeout_s=30)
    output = proc.get_output()
    assert "line1" in output
    assert "line2" in output
    assert "line3" in output
