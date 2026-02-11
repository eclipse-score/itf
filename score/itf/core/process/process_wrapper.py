# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
import signal
import subprocess
import time
import os
import pytest

from subprocess import TimeoutExpired
from score.itf.core.process.console import PipeConsole


logger = logging.getLogger(__name__)


class ProcessWrapper:
    """
    Simple process wrapper that ensure correct process termination upon timeout received from Bazel
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        binary_path,
        args=None,
        logger_name=None,
        env=None,
        cwd=None,
        monitor_process_startup=False,
        monitor_process_time=10.0,
    ):
        self._process = None
        self._old_sigterm = None
        self._binary_path = binary_path
        self._args = args
        self._logger_name = logger_name if logger_name is not None else os.path.basename(binary_path)
        self._env = env
        self._cwd = cwd
        self._console = None
        self._monitor_process_startup = monitor_process_startup
        self._monitor_process_time = monitor_process_time

    @property
    def process(self):
        return self._process

    @property
    def pid(self):
        return self._process.pid

    def __enter__(self):
        self.start_process(self._args)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.kill_process()

    def _signal_handler(self, signalnum, frame):
        logger.debug(f"Received signal: {signalnum} on frame: {frame}")
        self.kill_process()

    def start_process(self, override_args=None):
        # Add handler for SIGTERM, which will be fired by Bazel when test timeouts
        self._old_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
        cmd_line_args = [self._binary_path]

        if override_args is not None:  # Do not check for "True" to also allow for an empty array
            cmd_line_args.extend(override_args)
        elif self._args:
            cmd_line_args.extend(self._args)

        logger.info(f"Starting process: {' '.join(cmd_line_args)}")
        self._process = subprocess.Popen(
            cmd_line_args,
            start_new_session=True,
            env=self._env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE if self._logger_name else subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=self._cwd,
        )

        self._console = PipeConsole(self._logger_name, self._process)

        logger.info(f"Process [{self._binary_path}] started with PID: [{self._process.pid}]")
        if self._monitor_process_startup:
            self.monitor_process(self._monitor_process_time)

        return self

    def kill_process(self):
        return_code = self._process.poll()
        if return_code is not None:
            logger.warning(
                f"Process [{self._binary_path}] with PID: [{self._process.pid}] has already terminated "
                f"before, with return code: [{return_code}]."
            )
        else:
            try:
                pgrp = os.getpgid(self._process.pid)
                try:
                    logger.info(
                        f"Stopping process [{self._binary_path}] with PID: [{self._process.pid}] by sending SIGTERM to its PGID: [{pgrp}]"
                    )
                    os.killpg(pgrp, signal.SIGTERM)
                    self._process.wait(5)
                    logger.info(f"Process [{self._binary_path}] with PID: [{self._process.pid}] stopped")
                except subprocess.TimeoutExpired:
                    logger.info(
                        f"Process [{self._binary_path}] with PID: [{self._process.pid}] could not be stopped with SIGTERM, sending SIGKILL"
                    )
                    os.killpg(pgrp, signal.SIGKILL)
                    self._process.wait(5)
                    logger.info(f"Process [{self._binary_path}] with PID: [{self._process.pid}] forcefully killed")
                except OSError:
                    logger.exception(
                        f"Process [{self._binary_path}] with PID: [{self._process.pid}] could not be stopped"
                    )
            except ProcessLookupError:
                logger.warning(
                    f"Process [{self._binary_path}] with PID: [{self._process.pid}] could no longer be found"
                )
            except subprocess.TimeoutExpired:
                logger.error(f"Process [{self._binary_path}] failed to stop within the timeout period")

        logger.info("Restoring the old SIGTERM handler.")
        # Restore old SIGTERM handler
        signal.signal(signal.SIGTERM, self._old_sigterm)
        logger.info("Restoring done.")

    @property
    def console(self):
        return self._console

    def is_running(self):
        if not self._process:
            return False

        # poll() will return the exit code, if set, otherwise None;
        return self._process.poll() is None

    def wait_to_finish(self, timeout):
        try:
            return_code = self._process.wait(timeout)
            if return_code != 0:
                raise RuntimeError(
                    f"Process [{self._binary_path}] with PID: [{self._process.pid}]) finished with "
                    f"error code {return_code}."
                )
            logger.debug(f"Process [{self._binary_path}] with PID: [{self._process.pid}]) finished successfully.")
        except TimeoutExpired as original_exception:
            self.kill_process()
            raise RuntimeError(
                f"Process [{self._binary_path}] with PID: [{self._process.pid}]) didn't finish "
                f"for timeout of {timeout} seconds."
            ) from original_exception

    def monitor_process(self, time_interval):
        logger.info(f"Monitoring Process [{self._binary_path}] with PID: [{self._process.pid}].")
        start_time = time.time()
        while time.time() < start_time + time_interval:
            if not self.is_running():
                pytest.exit(f"Failed to start Process [{self._binary_path}] with PID: [{self._process.pid}]")
                break
            time.sleep(1)

    def restart_process(self, extra_args):
        override_args = None
        if extra_args:
            override_args = self._args + extra_args
            logger.info(f"Restarting {self._binary_path} with args: {override_args}")
        self.kill_process()
        self.start_process(override_args)
