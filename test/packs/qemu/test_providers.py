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
"""QEMU providers without QEMU: configuration-derived endpoint and login, the console, preconditions."""

import json
import re
import threading
import time

import pytest

from score.itf.core.process.console import try_to_decode
from score.itf.packs.qemu.console import QemuConsole
from score.itf.packs.qemu.descriptors import QemuCredentials, QemuEndpoint
from score.itf.packs.qemu.platform import QemuPlatform

BASE = {
    "networks": [{"name": "tap0", "ip_address": "169.254.158.190", "gateway": "169.254.21.88"}],
    "ssh_port": 2222,
    "qemu_num_cores": 2,
    "qemu_ram_size": "1G",
}


def _platform(tmp_path, **extra):
    config = tmp_path / "qemu.json"
    config.write_text(json.dumps({**BASE, **extra}), encoding="utf-8")
    return QemuPlatform({"config_file": str(config), "kernel": "ifs.img"})


def test_endpoint_is_the_first_network_and_ssh_port(tmp_path):
    endpoint = QemuEndpoint(_platform(tmp_path))
    assert (endpoint.host, endpoint.port) == ("169.254.158.190", 2222)


@pytest.mark.parametrize(
    "ssh_auth, expected",
    [
        (None, ("root", "", None)),
        ({"username": "qnxuser", "password": "qnxuser"}, ("qnxuser", "qnxuser", None)),
        ({"username": "root", "pkey_path": "/keys/id"}, ("root", None, "/keys/id")),
    ],
)
def test_credentials_follow_ssh_auth(tmp_path, ssh_auth, expected):
    extra = {"ssh_auth": ssh_auth} if ssh_auth else {}
    credentials = QemuCredentials(_platform(tmp_path, **extra))
    assert (credentials.user, credentials.password, credentials.key_path) == expected


def test_credentials_reject_an_empty_username(tmp_path):
    with pytest.raises(ValueError, match="username"):
        QemuCredentials(_platform(tmp_path, ssh_auth={"username": ""}))


def test_platform_needs_a_kernel_or_a_rootfs(tmp_path):
    config = tmp_path / "qemu.json"
    config.write_text(json.dumps(BASE), encoding="utf-8")
    with pytest.raises(ValueError, match="kernel, a rootfs"):
        QemuPlatform({"config_file": str(config)})


def test_start_without_qemu_installed_names_the_missing_binary(tmp_path):
    platform = _platform(tmp_path)
    platform.binary_dir = str(tmp_path / "nowhere")
    with pytest.raises(RuntimeError, match="qemu-system-x86_64 is missing"):
        platform.start()


class _FakePipeConsole:
    """Echoes what is written, then prints the exit-status marker, like a shell on a UART."""

    def __init__(self):
        self._lines: list[str] = []
        self._cv = threading.Condition()

    def emit(self, line: str) -> None:
        with self._cv:
            self._lines.append(line)
            self._cv.notify()

    def readline(self, block=False, timeout=None):
        with self._cv:
            if not self._lines:
                self._cv.wait(timeout)
            if not self._lines:
                raise TimeoutError
            return self._lines.pop(0)

    def write(self, text: str) -> None:
        command, _, _ = text.partition("; printf ")
        marker = re.search(r"ITF_DONE_[0-9a-f]+", text).group(0)
        self.emit(text)
        self.emit("hello" if "echo hello" in command else "")
        self.emit(marker + ("=3" if "false" in command else "=0"))


class _Platform:
    def __init__(self):
        self.console = _FakePipeConsole()


def test_console_records_lines_and_runs_commands():
    platform = _Platform()
    console = QemuConsole(platform)
    console.open()
    try:
        platform.console.emit("U-Boot 2026.01")
        assert console.wait_for("U-Boot", timeout=5, since=0) == "U-Boot 2026.01"
        mark = console.mark()
        code, output = console.run("echo hello", timeout=5)
        assert code == 0 and "hello" in output
        assert console.run("false", timeout=5)[0] == 3
        assert all("U-Boot" not in line for line in console.lines(mark))
    finally:
        console.close()
    assert not console.is_open()


def test_console_wait_for_times_out_with_none():
    console = QemuConsole(_Platform())
    console.open()
    try:
        started = time.monotonic()
        assert console.wait_for("never", timeout=0.3) is None
        assert time.monotonic() - started >= 0.3
    finally:
        console.close()


@pytest.mark.parametrize(
    "raw_output",
    [
        b"\rconsole_payload\n",
        b"\rconsole_payload\r\n",
        b"\x1b[?2004l\rconsole_payload\r\n",
        b"\r\x1b[?2004lconsole_payload\r\n",
    ],
)
def test_console_run_preserves_output_after_carriage_return(raw_output):
    class Terminal(_FakePipeConsole):
        def write(self, text):
            marker = re.search(r"ITF_DONE_[0-9a-f]+", text).group(0)
            self.emit(try_to_decode(raw_output))
            self.emit(marker + "=7")

    platform = _Platform()
    platform.console = Terminal()
    console = QemuConsole(platform)
    console.open()
    try:
        assert console.run("printf console_payload; sh -c 'exit 7'", timeout=5) == (7, "console_payload")
    finally:
        console.close()


class _FakeQemuProcess:
    """Stands in for the QEMU process: alive from start_process until killed or died."""

    instances: list = []

    def __init__(self, binary, args, logger_name=None, console_callbacks=None):
        self.console_callbacks = console_callbacks
        self.alive = False
        self.console = object()
        self.exit = 0
        _FakeQemuProcess.instances.append(self)

    def start_process(self):
        self.alive = True

    def is_running(self):
        return self.alive

    def kill_process(self):
        self.alive = False

    def exit_code(self):
        return self.exit


@pytest.fixture
def qemu_process(mocker, tmp_path):
    _FakeQemuProcess.instances.clear()
    mocker.patch("score.itf.packs.qemu.qemu.ProcessWrapper", _FakeQemuProcess)
    (tmp_path / "qemu-system-x86_64").write_text("", encoding="utf-8")
    return _FakeQemuProcess


def test_platform_is_running_between_start_and_stop(tmp_path, qemu_process):
    platform = _platform(tmp_path)
    platform.binary_dir = str(tmp_path)
    assert platform.running() is False
    platform.start()
    assert platform.running() is True
    platform.stop()
    assert platform.running() is False
    assert qemu_process.instances[0].alive is False


def test_platform_reports_a_qemu_that_died(tmp_path, qemu_process):
    platform = _platform(tmp_path)
    platform.binary_dir = str(tmp_path)
    platform.start()
    qemu_process.instances[0].alive = False
    assert platform.running() is False
    platform.stop()


def test_stopping_a_platform_that_never_started_is_harmless(tmp_path):
    platform = _platform(tmp_path)
    platform.stop()
    assert platform.running() is False
