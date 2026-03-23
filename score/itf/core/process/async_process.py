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
from abc import ABC, abstractmethod


class AsyncProcess(ABC):
    """Common interface for a non-blocking process execution handle.

    Target implementation must conform to this contract so that :class:`WrappedProcess` can
    manage process lifecycles regardless of the underlying execution backend.
    """

    @abstractmethod
    def pid(self) -> int:
        """Return the PID of the running process."""

    @abstractmethod
    def is_running(self) -> bool:
        """Return ``True`` if the process is still executing."""

    @abstractmethod
    def get_exit_code(self) -> int:
        """Return the exit code of the finished process.

        The result is only meaningful after the process has stopped.
        """

    @abstractmethod
    def stop(self) -> int:
        """Terminate the running process, escalating to ``SIGKILL`` if needed.

        :return: exit code of the stopped process.
        """

    @abstractmethod
    def wait(self, timeout_s: float = 15) -> int:
        """Block until the process finishes or *timeout_s* elapses.

        :param timeout_s: maximum seconds to wait.
        :return: exit code of the process.
        :raises RuntimeError: on timeout.
        """

    @abstractmethod
    def get_output(self) -> str:
        """Return the captured stdout of the process.

        Output is accumulated as the process runs.  It is safe to call
        while the process is still executing (returns what has been
        captured so far) or after it has finished.
        """
