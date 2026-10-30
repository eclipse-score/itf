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

import subprocess
import sys
import time

import pytest

import score.itf.plugins.qemu as qemu_plugin
from score.itf.plugins.qemu.qemu_process import QemuProcess


class FakeTarget:
    def __init__(self, panics_on_attempts):
        self._panics_on_attempts = panics_on_attempts
        self.boots = 1
        self.guest_panicked = False
        self.restarts = 0

    def run_checks(self):
        self.guest_panicked = self.boots in self._panics_on_attempts
        if self.guest_panicked:
            raise AssertionError("ssh failed")

    def restart(self):
        self.restarts += 1
        self.boots += 1
        self.guest_panicked = False


@pytest.fixture
def target(monkeypatch):
    def make(panics_on_attempts):
        fake = FakeTarget(panics_on_attempts)
        monkeypatch.setattr(qemu_plugin, "pre_tests_phase", lambda _target: fake.run_checks())
        return fake

    return make


def test_no_restart_when_boot_succeeds(target):
    fake = target(panics_on_attempts=[])
    qemu_plugin._boot_until_ready(fake, max_attempts=3)
    assert fake.restarts == 0


def test_restarts_after_guest_panic(target):
    fake = target(panics_on_attempts=[1, 2])
    qemu_plugin._boot_until_ready(fake, max_attempts=3)
    assert fake.restarts == 2


def test_raises_when_every_attempt_panics(target):
    fake = target(panics_on_attempts=[1, 2, 3])
    with pytest.raises(AssertionError):
        qemu_plugin._boot_until_ready(fake, max_attempts=3)
    assert fake.restarts == 2


def test_failure_without_panic_is_not_retried(monkeypatch):
    fake = FakeTarget(panics_on_attempts=[])

    def failing_checks(_target):
        raise AssertionError("not a panic")

    monkeypatch.setattr(qemu_plugin, "pre_tests_phase", failing_checks)
    with pytest.raises(AssertionError):
        qemu_plugin._boot_until_ready(fake, max_attempts=3)
    assert fake.restarts == 0


def test_console_panic_marker_flags_process_and_terminates_qemu(monkeypatch):
    monkeypatch.setattr("score.itf.plugins.qemu.qemu.Qemu._Qemu__check_qemu_is_installed", lambda self: None)
    script = "import time; print('Shutdown[1] S/C/F=5/4/3 muon', flush=True); time.sleep(60)"
    monkeypatch.setattr(
        "score.itf.plugins.qemu.qemu.Qemu._Qemu__build_qemu_command",
        lambda self: [sys.executable, "-c", script],
    )
    process = QemuProcess(None, "1G", 1, [], [], "pc-x86_64", None, None, None)
    process.start()
    try:
        deadline = time.time() + 10
        while not process.guest_panicked and time.time() < deadline:
            time.sleep(0.05)
        assert process.guest_panicked
        assert process._qemu._subprocess.wait(timeout=10) is not None
    finally:
        if process._qemu._subprocess.poll() is None:
            process._qemu._subprocess.kill()
