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
import logging
import os
import signal

from score.itf.core.process.async_process import AsyncProcess


logger = logging.getLogger(__name__)


class WrappedProcess:
    """Unified process wrapper that works with any Target implementation.

    Manages the lifecycle of a binary executed asynchronously through the
    ``Target.execute_async()`` → ``AsyncProcess`` interface.
    """

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments

    def __init__(
        self,
        target,
        binary_path,
        args=None,
        cwd="/",
        wait_on_exit=False,
        wait_timeout=15,
        enforce_clean_shutdown=False,
        expected_exit_code=0,
        **kwargs,
    ):
        self.target = target
        self.binary_path = binary_path
        self.args = args if args is not None else []
        self.cwd = cwd

        self.ret_code = None
        self.process = None

        self._wait_on_exit = wait_on_exit
        self._wait_timeout = wait_timeout
        self.enforce_clean_shutdown = enforce_clean_shutdown
        self.expected_exit_code = expected_exit_code
        self.kwargs = kwargs

    def __enter__(self):
        self.process = self.target.execute_async(self.binary_path, args=self.args, cwd=self.cwd, **self.kwargs)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.ret_code = self._handle_process_exit()
        logger.debug(f"Application [{os.path.basename(self.binary_path)}] exit code: [{self.ret_code}]")
        self._check_process_exit_code()

    def pid(self):
        return self.process.pid()

    def is_running(self):
        return self.process.is_running()

    def get_exit_code(self):
        return self.process.get_exit_code()

    def stop(self):
        return self.process.stop()

    def wait(self, timeout_s=15):
        return self.process.wait(timeout_s)

    def get_output(self):
        """Return the captured stdout of the process."""
        return self.process.get_output()

    def _handle_process_exit(self):
        if self._wait_on_exit:
            return self.process.wait(self._wait_timeout)
        # don't wait for process natural finish, just terminate it
        if self.process.is_running():
            return self.process.stop()
        return self.process.get_exit_code()

    def _check_process_exit_code(self):
        signal_base = 128
        acceptable_exit_codes = {
            0,
            signal_base + signal.SIGTERM,
            self.expected_exit_code,
        }

        # If clean shutdown is not enforced, then SIGKILL is an acceptable exit code
        if not self.enforce_clean_shutdown:
            acceptable_exit_codes.add(signal_base + signal.SIGKILL)

        if self.ret_code not in acceptable_exit_codes:
            if self.ret_code == 55:
                raise RuntimeError("Sanitizers failed")
            if self.ret_code == signal_base + signal.SIGKILL:
                raise RuntimeError(
                    f"Application [{self.binary_path}] exit code: [{self.ret_code}] indicates it was stopped with SIGKILL,"
                    " so it did not shut down gracefully, but enforce_clean_shutdown is flagged as True"
                )
            if self.ret_code == signal_base + signal.SIGSEGV:
                raise RuntimeError(
                    f"Application [{self.binary_path}] exit code: [{self.ret_code}] indicates SIGSEGV occurred."
                )
            if self.ret_code == signal_base + signal.SIGABRT:
                raise RuntimeError(
                    f"Application [{self.binary_path}] exit code: [{self.ret_code}] indicates SIGABRT occurred."
                )
            raise RuntimeError(f"Application [{self.binary_path}] exit code: [{self.ret_code}] indicates an error.")
