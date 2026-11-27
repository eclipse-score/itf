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
"""Conformance of the exec area: command, process, shell, console."""

import uuid

from score.itf.contracts.conformance import check, expect

COMMAND = "exec.command"
PROCESS = "exec.process"
SHELL = "exec.shell"
CONSOLE = "exec.console"


# -- command ---------------------------------------------------------------------------------------


@check()
def output_and_exit_code_are_returned(node):
    result = node.exec("echo -n hello")
    expect(result == (0, b"hello"), f"exec('echo -n hello') returned {result!r}, expected (0, b'hello')")


@check()
def a_failing_command_reports_its_exit_code_without_raising(node):
    # A child shell: on a console the session itself persists, and a bare `exit` would end it.
    code, output = node.exec("sh -c 'exit 3'")
    expect(
        code == 3 and isinstance(output, bytes), f"exec of a command exiting 3 returned code {code} (output {output!r})"
    )


@check()
def stderr_is_part_of_the_output(node):
    code, output = node.exec("echo oops >&2")
    expect(
        code == 0 and isinstance(output, bytes) and b"oops" in output,
        f"stderr text missing from the output: ({code}, {output!r})",
    )


CHECKS = {
    COMMAND: [
        output_and_exit_code_are_returned,
        a_failing_command_reports_its_exit_code_without_raising,
        stderr_is_part_of_the_output,
    ]
}


# -- process ---------------------------------------------------------------------------------------


@check()
def a_process_reports_pid_running_and_exit_code(node):
    process = node.spawn("sleep 1; exit 42")
    expect(process.pid() > 0, f"pid() returned {process.pid()!r}, expected a positive number")
    expect(process.is_running(), "is_running() is false right after spawn of a one second job")
    code = process.wait(timeout_s=30)
    expect(code == 42, f"wait() returned {code!r}, expected the exit code 42")
    expect(not process.is_running(), "is_running() is still true after wait() returned")


@check()
def stop_terminates_a_long_running_process(node):
    process = node.spawn("sleep 300")
    code = process.stop()
    expect(code in (143, 137), f"stop() returned {code!r}, expected 143 (SIGTERM) or 137 (SIGKILL)")
    expect(not process.is_running(), "is_running() is still true after stop()")


@check()
def output_is_captured(node):
    process = node.spawn("echo first; echo second")
    process.wait(timeout_s=30)
    expect(
        process.get_output().split() == ["first", "second"],
        f"get_output() returned {process.get_output()!r}, expected the two lines 'first' and 'second'",
    )


@check()
def cwd_is_honoured(node):
    process = node.spawn("pwd", cwd="/tmp")
    code = process.wait(timeout_s=30)
    expect(code == 0 and "/tmp" in process.get_output(), f"pwd in cwd='/tmp' gave ({code}, {process.get_output()!r})")


CHECKS[PROCESS] = [
    a_process_reports_pid_running_and_exit_code,
    stop_terminates_a_long_running_process,
    output_is_captured,
    cwd_is_honoured,
]


# -- shell -----------------------------------------------------------------------------------------


@check()
def execute_command_returns_the_exit_code(node):
    code = node.execute_command("exit 4")
    expect(code == 4, f"execute_command('exit 4') returned {code}")


@check()
def stdout_and_stderr_can_be_kept_apart_or_merged(node):
    command = "echo out; echo err 1>&2; exit 7"
    code, out, err = node.execute_command_output(command, separate_stderr=True)
    expect(code == 7 and "out" in "".join(out) and "err" in "".join(err), f"separate: got ({code}, {out!r}, {err!r})")
    code, out, err = node.execute_command_output(command, separate_stderr=False)
    expect(err == [] and "err" in "".join(out), f"merged: got ({code}, {out!r}, {err!r}); stderr should be in stdout")


@check()
def line_splitting_is_preserved(node):
    result = node.execute_command_output("printf 'a\\nb\\n'")
    expect(
        result == (0, ["a\n", "b\n"], []),
        f"execute_command_output returned {result!r}, expected (0, ['a\\n', 'b\\n'], [])",
    )


@check()
def a_command_running_too_long_reports_minus_one(node):
    code = node.execute_command_output("sleep 5", max_exec_time=1)[0]
    expect(code == -1, f"execute_command_output over max_exec_time returned code {code}, expected -1")


CHECKS[SHELL] = [
    execute_command_returns_the_exit_code,
    stdout_and_stderr_can_be_kept_apart_or_merged,
    line_splitting_is_preserved,
    a_command_running_too_long_reports_minus_one,
]


# -- console ---------------------------------------------------------------------------------------


@check()
def the_console_is_open(node):
    expect(node.is_open(), "is_open() is false although the state console.open holds")


@check()
def the_console_recorded_output_since_it_opened(node):
    expect(node.lines(), "the console recorded nothing since it opened (not even the boot or prompt text)")


@check()
def run_reports_the_exit_code_and_the_output(node):
    code, output = node.run("echo -n hi")
    expect(code == 0 and "hi" in output, f"run('echo -n hi') returned ({code}, {output!r})")
    code, _ = node.run("sh -c 'exit 3'")
    expect(code == 3, f"run of a command exiting 3 returned code {code}")


@check()
def written_text_is_seen_after_a_mark(node):
    token = f"itf-{uuid.uuid4().hex[:8]}"
    before = node.lines()
    cursor = node.mark()
    node.write(f"echo {token[:4]}''{token[4:]}")  # the echoed command line differs from the printed result
    found = node.wait_for(token, timeout=15, since=cursor)
    if found is None:
        raise AssertionError(f"wait_for({token!r}) saw nothing within 15 s after write()")
    expect(token in "".join(node.lines(since=cursor)), "lines(since=mark) does not hold the line wait_for found")
    expect(token not in "".join(before), "the new token was already in the lines taken before the mark")
    expect(node.mark() >= cursor, "mark() went backwards")


CHECKS[CONSOLE] = [
    the_console_is_open,
    the_console_recorded_output_since_it_opened,
    run_reports_the_exit_code_and_the_output,
    written_text_is_seen_after_a_mark,
]
