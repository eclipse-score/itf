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
import queue
import threading
import time

import pytest

from score.itf.packs.serial.console import SerialConsole
from score.itf.packs.serial.providers import make_console, make_exec
from score.itf.packs.serial.steps import is_console_open, open_console


class FakePort:
    """A serial port whose remote side is a tiny shell answering `<cmd>; printf '\\n<marker>=%s\\n' $?`."""

    def __init__(self, responses=None):
        self.incoming: queue.Queue[bytes] = queue.Queue()
        self.written: list[bytes] = []
        self.responses = responses or {}
        self.closed = False
        self.in_waiting = 0

    def feed(self, data: bytes) -> None:
        self.incoming.put(data)

    def read(self, size: int) -> bytes:
        if self.closed:
            raise OSError("port closed")
        try:
            return self.incoming.get(timeout=0.05)
        except queue.Empty:
            return b""

    def write(self, data: bytes) -> None:
        self.written.append(data)
        line = data.decode().rstrip("\n")
        self.feed(line.encode() + b"\r\n")  # echo, as a tty does
        if "; printf " in line:
            command, printf = line.split("; printf ")
            marker = printf.split("\\n")[1].split("=")[0]
            code, output = self.responses.get(command, (0, ""))
            body = (output + "\r\n").encode() if output else b""
            self.feed(body + f"{marker}={code}".encode() + b"\r\n")

    def close(self) -> None:
        self.closed = True


def opened(port, **kwargs):
    console = SerialConsole("/dev/fake", opener=lambda *args: port, **kwargs)
    console.open()
    return console


def test_construction_and_probe_are_inert():
    calls = []
    console = SerialConsole("/dev/fake", opener=lambda *args: calls.append(args))
    assert is_console_open(console) is False
    assert calls == []
    console.close()


def test_open_captures_lines_split_across_reads_and_writes_log(tmp_path):
    port = FakePort()
    log = tmp_path / "console" / "isoc.log"
    console = opened(port, logfile=str(log))
    port.feed(b"IFS boot")
    port.feed(b"loader\r\nQNX up\r\npartial")
    assert console.wait_for("QNX up", timeout=2, since=0) == "QNX up"
    assert console.lines()[:2] == ["IFS bootloader", "QNX up"]
    console.close()
    assert "partial" in console.lines()
    assert "IFS bootloader" in log.read_text()


def test_run_returns_exit_code_and_output_without_echo():
    port = FakePort({"uname -a": (0, "QNX localhost 8.0.0"), "false": (1, "")})
    console = opened(port)
    assert console.run("uname -a", timeout=2) == (0, "QNX localhost 8.0.0")
    assert console.run("false", timeout=2) == (1, "")
    assert port.written[0] == b"uname -a; printf '\\nITF_DONE_1=%s\\n' $?\n"
    console.close()


def test_wait_for_ignores_history_unless_asked_and_supports_regex():
    port = FakePort()
    console = opened(port)
    port.feed(b"old ready\n")
    assert console.wait_for("old", timeout=2, since=0) == "old ready"
    assert console.wait_for("old", timeout=0.2) is None
    cursor = console.mark()
    port.feed(b"temp=41C\n")
    assert console.wait_for(r"temp=\d+C", timeout=2, since=cursor, regex=True) == "temp=41C"
    console.close()


def test_run_times_out_when_no_marker_arrives():
    class SilentPort(FakePort):
        def write(self, data):
            self.written.append(data)

    console = opened(SilentPort())
    with pytest.raises(TimeoutError, match="did not finish"):
        console.run("sleep 100", timeout=0.2)
    console.close()


def test_bounded_buffer_keeps_cursors_valid():
    port = FakePort()
    console = opened(port, buffer=3)
    for index in range(5):
        port.feed(f"line {index}\n".encode())
    assert console.wait_for("line 4", timeout=2, since=0) == "line 4"
    assert console.lines() == ["line 2", "line 3", "line 4"]
    assert console.lines(since=4) == ["line 4"]
    console.close()


def test_read_error_marks_console_closed():
    class FailingPort(FakePort):
        def read(self, size):
            raise OSError("unplugged")

    console = opened(FailingPort())
    deadline = time.monotonic() + 2
    while console.is_open() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert console.is_open() is False
    with pytest.raises(RuntimeError, match="not open"):
        console.write("ls")
    console.close()


def test_stuck_reader_reports_timeout_and_still_closes_port():
    release = threading.Event()

    class StuckPort(FakePort):
        def read(self, size):
            release.wait()
            return b""

    port = StuckPort()
    console = opened(port, stop_timeout=0.1)
    try:
        with pytest.raises(RuntimeError, match="did not stop"):
            console.close()
        assert port.closed
    finally:
        release.set()


def test_open_action_and_provider_teardown():
    port = FakePort()
    provider = make_console({"device": "/dev/fake"})
    console = next(provider)
    console._opener = lambda *args: port
    open_console(console)
    assert is_console_open(console)
    with pytest.raises(StopIteration):
        next(provider)
    assert port.closed and not console.is_open()


@pytest.mark.parametrize(
    "kwargs", [{"device": " "}, {"device": "/dev/x", "baudrate": 0}, {"device": "/dev/x", "read_timeout": 0}]
)
def test_invalid_configuration_is_rejected(kwargs):
    device = kwargs.pop("device")
    with pytest.raises(ValueError):
        SerialConsole(device, **kwargs)


def test_serial_exec_view_reuses_the_console():
    port = FakePort({"pidin info": (0, "QNX 8.0"), "false": (1, "")})
    console = opened(port)
    runner = make_exec(console)
    assert runner.console is console
    assert runner.exec("pidin info", timeout=2) == (0, b"QNX 8.0")
    assert runner.exec("false", timeout=2) == (1, b"")
    console.close()
