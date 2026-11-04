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
"""Asynchronous processes on their own SSH channels (`ssh.process`)."""

from __future__ import annotations

import logging
import os
import shlex
import signal
import threading
import time
from score.itf.core.process import AsyncProcess

from .command import Shell


class SshAsyncProcess(AsyncProcess):
    """A command on its own SSH channel. Signals go through the session, by the shell's PID."""

    def __init__(self, shell: Shell, channel, pid: int, output_thread: threading.Thread, output: list[str]):
        self._shell = shell
        self._channel = channel
        self._pid = pid
        self._output_thread = output_thread
        self._output = output
        self._logger = logging.getLogger(f"async_exec.{pid}")
        self._signalled = 0

    def pid(self) -> int:
        return self._pid

    def is_running(self) -> bool:
        return not self._channel.exit_status_ready()

    def get_exit_code(self) -> int:
        code = self._channel.recv_exit_status()
        # Ended by a signal, SSH reports no status (-1); report the shell convention instead,
        # 128 + the signal, like every other exec.process provider.
        return 128 + self._signalled if code == -1 and self._signalled else code

    def wait(self, timeout_s: float = 15) -> int:
        deadline = time.monotonic() + timeout_s
        while self.is_running():
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"Waiting for process with PID [{self._pid}] to terminate timed out after {timeout_s} seconds"
                )
            time.sleep(0.1)
        self._output_thread.join()
        return self.get_exit_code()

    def stop(self) -> int:
        self._signalled = signal.SIGTERM
        self._shell.execute_command(f"kill {self._pid}")
        for _ in range(5):
            time.sleep(1)
            if not self.is_running():
                break
        if self.is_running():
            self._logger.error("Process with PID [%s] did not terminate properly, sending SIGKILL.", self._pid)
            self._signalled = signal.SIGKILL
            self._shell.execute_command(f"kill -9 {self._pid}")
            self.wait()
        self._output_thread.join()
        return self.get_exit_code()

    def get_output(self) -> str:
        return "\n".join(self._output) + ("\n" if self._output else "")


class SshProcess:
    """`process`: `spawn` starts a command on a new channel and returns at once."""

    def __init__(self, shell: Shell):
        self.shell = shell

    def spawn(self, binary_path: str, args: list[str] | None = None, cwd: str = "/", **kwargs) -> SshAsyncProcess:
        command = " ".join([binary_path, *(shlex.quote(a) for a in (args or []))])
        channel = self.shell.get_paramiko_client().get_transport().open_session()
        channel.set_combine_stderr(True)
        # A simple command replaces the shell, so the PID printed is the program's own.
        run = command if any(c in command for c in ";&|()<>") else f"exec {command}"
        inner = f"[ -r /etc/profile ] && . /etc/profile >/dev/null 2>&1; echo $$; cd {shlex.quote(cwd)} && {run}"
        channel.exec_command(f"sh -lc {shlex.quote(inner)}")

        channel.settimeout(30)
        pid_line = b""
        while (byte := channel.recv(1)) and byte != b"\n":
            pid_line += byte
        channel.settimeout(None)
        pid = int(pid_line.decode().strip())

        cmd_logger = logging.getLogger(os.path.basename(binary_path.split()[0]))
        output: list[str] = []

        def pump() -> None:
            def receive() -> bool:
                data = channel.recv(4096)
                if not data:
                    return False
                for line in data.decode(errors="replace").strip().split("\n"):
                    cmd_logger.info(line)
                    output.append(line)
                return True

            while True:
                if channel.recv_ready():
                    if not receive():
                        return
                elif channel.exit_status_ready():
                    while channel.recv_ready() and receive():
                        pass
                    return
                else:
                    time.sleep(0.1)

        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        return SshAsyncProcess(self.shell, channel, pid, thread, output)

    def wrap_exec(self, *args, **kwargs):
        from score.itf.core.process import WrappedProcess

        return WrappedProcess(self, *args, **kwargs)
