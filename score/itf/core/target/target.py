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
from typing import List, Set, Optional, Tuple

from score.itf.core.process.async_process import AsyncProcess
from score.itf.core.process.wrapped_process import WrappedProcess


class Target(ABC):
    """Base target interface for test implementations.

    This class provides a common interface for targets that tests can implement against.
    Targets support a capability-based system that allows tests to query and make
    decisions based on available capabilities.

    Besides capability management, this base class defines a *minimum contract*
    that every concrete target implementation must provide.

    Required functionality:
    - exec command (`execute`)
    - upload/download file (`upload`, `download`)
    - restart target (`restart`)

    Example:
        class MyTarget(Target):
            def __init__(self):
                super().__init__(capabilities={'ssh', 'file_transfer'})

            def execute(self, command):
                # Implementation specific logic
                pass

        # In a test:
        if target.has_capability('ssh'):
            target.execute('ls -la')
    """

    REQUIRED_CAPABILITIES: Set[str] = {"exec", "file_transfer", "restart"}

    def __init__(self, capabilities: Optional[Set[str]] = None):
        """Initialize the target with a set of capabilities.

        Args:
            capabilities: Set of capability identifiers supported by this target.
                         If None, an empty set is used.
        """
        self._capabilities: Set[str] = set(capabilities) if capabilities is not None else set()
        self._capabilities.update(self.REQUIRED_CAPABILITIES)

    def has_capability(self, capability: str) -> bool:
        """Check if the target supports a specific capability."""

        return capability in self._capabilities

    def has_all_capabilities(self, capabilities: Set[str]) -> bool:
        """Check if the target supports all of the specified capabilities."""

        return capabilities.issubset(self._capabilities)

    def has_any_capability(self, capabilities: Set[str]) -> bool:
        """Check if the target supports any of the specified capabilities."""

        return bool(capabilities.intersection(self._capabilities))

    def get_capabilities(self) -> Set[str]:
        """Get all capabilities supported by this target."""

        return self._capabilities.copy()

    def add_capability(self, capability: str) -> None:
        """Add a capability to the target."""

        self._capabilities.add(capability)

    def remove_capability(self, capability: str) -> None:
        """Remove a capability from the target."""

        self._capabilities.discard(capability)

    @abstractmethod
    def execute(self, command: str) -> Tuple[int, bytes]:
        """Execute a command on the target."""

    @abstractmethod
    def execute_async(
        self,
        binary_path: str,
        args: Optional[List[str]] = None,
        cwd: str = "/",
    ) -> AsyncProcess:
        """Start a binary without blocking and return an :class:`AsyncProcess` handle.

        :param binary_path: path to the binary to execute.
        :param args: list of string arguments for the binary (default: ``None``).
        :param cwd: working directory inside the target environment.
        :return: an :class:`AsyncProcess` instance.
        """

    def wrap_exec(
        self,
        *args,
        **kwargs,
    ) -> WrappedProcess:
        return WrappedProcess(
            self,
            *args,
            **kwargs,
        )

    @abstractmethod
    def upload(self, local_path: str, remote_path: str) -> None:
        """Upload a file from the test host to the target."""

    @abstractmethod
    def download(self, remote_path: str, local_path: str) -> None:
        """Download a file from the target to the test host."""

    @abstractmethod
    def restart(self) -> None:
        """Restart the target environment."""


class UnsupportedTarget(Target):
    """Fallback target used when no concrete target plugin is selected."""

    REQUIRED_CAPABILITIES: Set[str] = set()

    def execute(self, command: str) -> Tuple[int, bytes]:
        raise NotImplementedError("No target plugin selected: exec is unavailable")

    def execute_async(self, binary_path: str, args: Optional[List[str]] = None, cwd: str = "/") -> AsyncProcess:
        raise NotImplementedError("No target plugin selected: exec is unavailable")

    def upload(self, local_path: str, remote_path: str) -> None:
        raise NotImplementedError("No target plugin selected: upload is unavailable")

    def download(self, remote_path: str, local_path: str) -> None:
        raise NotImplementedError("No target plugin selected: download is unavailable")

    def restart(self) -> None:
        raise NotImplementedError("No target plugin selected: restart is unavailable")
