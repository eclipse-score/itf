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

logger = logging.getLogger(__name__)


class SshCommand:
    """This class allows to start executing commands via ssh in the
    background and retrieve the results at a later point in time."""

    def __init__(self, ssh_connection, cmd, ssh_connection_timeout=None):
        """Immediately executes the command"""
        _, self.__stdout, self.__stderr = ssh_connection.exec_command(cmd, timeout=ssh_connection_timeout)
        self.__stdout_bytes = None
        self.__stderr_bytes = None
        self.__exit_status = None

    def wait_until_finished(self, command_result_timeout) -> "SshCommandResult":
        """Block until the command terminates."""
        logger.debug("Setting timeout on channel.")
        self.__stdout.channel.settimeout(command_result_timeout)
        logger.debug("Trying to read stdout.")
        self.__stdout_bytes = self.__stdout.read()
        logger.debug("Trying to read stderr.")
        self.__stderr_bytes = self.__stderr.read()
        logger.debug("Trying to read exit_status.")
        self.__exit_status = self.__stdout.channel.recv_exit_status()
        return SshCommandResult(self.__stdout_bytes, self.__stderr_bytes, self.__exit_status)

    def is_finished(self) -> bool:
        """Checks if the ssh command has already exited."""
        return self.__stdout.channel.exit_status_ready()


class SshCommandResult:
    def __init__(self, stdout, stderr, exit_code):
        self.__stdout = stdout
        self.__stderr = stderr
        self.__exit_code = exit_code

    def get_stdout_bytes(self):
        """Return the stdout in bytes."""
        return self.__stdout

    def get_stderr_bytes(self):
        """Return the stderr in bytes."""
        return self.__stderr

    def get_exit_code(self):
        """Return the exit code"""
        return self.__exit_code
