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

from typing import Set, Optional, Any, Dict


class Target:
    """Base target interface for test implementations.

    This class provides a common interface for targets that tests can implement against.
    Targets support a capability-based system that allows tests to query and make
    decisions based on available capabilities.

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

    def __init__(self, capabilities: Optional[Set[str]] = None):
        """Initialize the target with a set of capabilities.

        Args:
            capabilities: Set of capability identifiers supported by this target.
                         If None, an empty set is used.
        """
        self._capabilities: Set[str] = capabilities if capabilities is not None else set()

    def has_capability(self, capability: str) -> bool:
        """Check if the target supports a specific capability.

        Args:
            capability: The capability identifier to check.

        Returns:
            True if the capability is supported, False otherwise.
        """
        return capability in self._capabilities

    def has_all_capabilities(self, capabilities: Set[str]) -> bool:
        """Check if the target supports all of the specified capabilities.

        Args:
            capabilities: Set of capability identifiers to check.

        Returns:
            True if all capabilities are supported, False otherwise.
        """
        return capabilities.issubset(self._capabilities)

    def has_any_capability(self, capabilities: Set[str]) -> bool:
        """Check if the target supports any of the specified capabilities.

        Args:
            capabilities: Set of capability identifiers to check.

        Returns:
            True if at least one capability is supported, False otherwise.
        """
        return bool(capabilities.intersection(self._capabilities))

    def get_capabilities(self) -> Set[str]:
        """Get all capabilities supported by this target.

        Returns:
            Set of all capability identifiers.
        """
        return self._capabilities.copy()

    def add_capability(self, capability: str) -> None:
        """Add a capability to the target.

        Args:
            capability: The capability identifier to add.
        """
        self._capabilities.add(capability)

    def remove_capability(self, capability: str) -> None:
        """Remove a capability from the target.

        Args:
            capability: The capability identifier to remove.
        """
        self._capabilities.discard(capability)
