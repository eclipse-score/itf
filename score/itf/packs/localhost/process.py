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
"""Asynchronous processes on the host (`localhost.process`)."""

from __future__ import annotations

import os
import shlex

from score.itf.core.process import AsyncProcess, ProcessWrapper

from .command import Platform


class LocalAsyncProcess(AsyncProcess):
    """An `AsyncProcess` over a tracked `ProcessWrapper`: the wrapper owns starting, logging and stopping."""

    def __init__(self, wrapper: ProcessWrapper):
        self._wrapper = wrapper

    def pid(self) -> int:
        return self._wrapper.pid

    def is_running(self) -> bool:
        return self._wrapper.is_running()

    def get_exit_code(self) -> int:
        self._wrapper.process.wait()
        # the console's reader thread may still be handing over the last lines
        self._wrapper.console.line_reader.join(timeout=2)
        return self._wrapper.exit_code()

    def wait(self, timeout_s: float = 15) -> int:
        try:
            self._wrapper.process.wait(timeout_s)
        except Exception as exc:
            raise RuntimeError(
                f"Waiting for process with PID [{self.pid()}] to terminate timed out after {timeout_s} seconds"
            ) from exc
        return self.get_exit_code()

    def stop(self) -> int:
        self._wrapper.kill_process()
        return self.get_exit_code()

    def get_output(self) -> str:
        return self._wrapper.output()


class LocalProcess:
    def __init__(self, platform: Platform):
        self.platform = platform

    def spawn(self, binary_path: str, args: list[str] | None = None, cwd: str = "/") -> LocalAsyncProcess:
        command = " ".join([binary_path, *(shlex.quote(a) for a in (args or []))])
        wrapper = ProcessWrapper(
            "/bin/sh",
            ["-c", f"exec {command}" if not any(c in command for c in ";&|") else command],
            logger_name=os.path.basename(binary_path.split()[0]),
            cwd=cwd,
            keep_output=True,
        )
        wrapper.start_process()
        return LocalAsyncProcess(wrapper)
