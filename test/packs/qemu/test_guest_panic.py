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
"""A guest kernel panic on the console: recorded, and QEMU stopped at once (ported from main's boot retry)."""

import sys
import threading
import time

from score.itf.core.process import ProcessWrapper
from score.itf.packs.qemu.platform import GUEST_PANIC_MARKER, QemuPlatform


class Qemu:
    """Stands in for the QEMU process: a Python process that prints what a guest console would."""

    def __init__(self, lines):
        self.lines = lines
        self.wrapper = None

    def start(self, console_callbacks=None):
        script = "import time\n" + "".join(f"print({line!r}, flush=True)\n" for line in self.lines) + "time.sleep(60)\n"
        self.wrapper = ProcessWrapper(sys.executable, ["-c", script], console_callbacks=console_callbacks)
        self.wrapper.start_process()
        return self.wrapper

    def is_running(self):
        return self.wrapper is not None and self.wrapper.is_running()

    def terminate(self):
        self.wrapper.terminate()


def platform_with(qemu) -> QemuPlatform:
    platform = QemuPlatform.__new__(QemuPlatform)  # no configuration file: only the console watch is under test
    platform.panic_marker = GUEST_PANIC_MARKER
    platform._qemu = qemu
    platform._guest_panicked = threading.Event()
    return platform


def started(platform, qemu):
    platform._guest_panicked.clear()
    platform.console = qemu.start(console_callbacks=[(platform.panic_marker, platform._on_guest_panic)]).console


def test_a_panic_on_the_console_is_recorded_and_stops_qemu_at_once():
    qemu = Qemu(["booting", "Shutdown[1] S/C/F=5/4/3 C/D=ff810000/ff8a7000 state(c0)= now lock"])
    platform = platform_with(qemu)
    started(platform, qemu)
    deadline = time.monotonic() + 10
    while qemu.is_running() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert platform.guest_panicked
    assert not qemu.is_running(), "QEMU should be stopped as soon as the panic is seen, not after 60 s"


def test_a_clean_boot_is_not_a_panic():
    qemu = Qemu(["booting", "login:"])
    platform = platform_with(qemu)
    started(platform, qemu)
    time.sleep(1)
    try:
        assert not platform.guest_panicked and qemu.is_running()
    finally:
        qemu.wrapper.kill_process()
