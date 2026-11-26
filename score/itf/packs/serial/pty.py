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
"""A serial port backed by a shell on a pseudo-terminal: a UART with something answering.

For benches without hardware: the same `SerialConsole` reads and writes it, so boot banners,
`wait_for`, `run` and exec-over-console behave as on a device whose console is a shell. Linux and
macOS only (it needs `pty`).
"""

from __future__ import annotations

import fcntl
import os
import select
import struct
import termios
from dataclasses import dataclass

from score.itf.core.process import ProcessWrapper


@dataclass(frozen=True)
class PtyConsoleConfig:
    shell: str = "/bin/sh"
    banner: str = "ITF PTY CONSOLE READY"
    logfile: str | None = None
    buffer: int = 20000
    read_timeout: float = 0.2
    stop_timeout: float = 5.0


class PtyPort:
    """The part of pyserial's Serial that `SerialConsole` uses, over a shell's terminal."""

    def __init__(self, shell: str, banner: str, read_timeout: float):
        import pty

        master, slave = pty.openpty()
        attributes = termios.tcgetattr(slave)
        attributes[3] &= ~termios.ECHO  # the terminal does not echo: output is the shell's own
        termios.tcsetattr(slave, termios.TCSANOW, attributes)
        # A read-eval loop, not an interactive shell: no prompt, no line editing and plain SIGTERM handling
        # (bash turns interactive on a terminal by itself). Lines run in one shell, so state persists.
        loop = 'while IFS= read -r line; do eval "$line"; done'
        script = f"echo \"$ITF_BANNER\"; exec {shell} -c '{loop}'"
        self._process = ProcessWrapper(
            shell,
            ["-c", script],
            logger_name="serial.pty",
            stdio={"stdin": slave, "stdout": slave, "stderr": slave},
            env={**os.environ, "ITF_BANNER": banner},
        )
        self._process.start_process()
        os.close(slave)
        self._fd = master
        self._timeout = read_timeout

    @property
    def in_waiting(self) -> int:
        return struct.unpack("i", fcntl.ioctl(self._fd, termios.FIONREAD, b"\0\0\0\0"))[0]

    def read(self, size: int = 1) -> bytes:
        if not select.select([self._fd], [], [], self._timeout)[0]:
            return b""
        try:
            return os.read(self._fd, size)
        except OSError:  # the shell exited: the terminal reports EIO
            return b""

    def write(self, data: bytes) -> int:
        return os.write(self._fd, data)

    def flush(self) -> None:
        termios.tcdrain(self._fd)

    def close(self) -> None:
        try:
            self._process.kill_process()
        finally:
            try:
                os.close(self._fd)
            except OSError:
                pass


def pty_opener(shell: str, banner: str):
    """An opener for `SerialConsole`: ignores the device and baud rate, starts the shell."""
    return lambda _device, _baudrate, read_timeout: PtyPort(shell, banner, read_timeout)
