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
"""Facades: a project's own target API over a composed target, so its tests keep their shape and only the
infrastructure below them changes.

A facade is a plain class. Its methods are the project's own API, written over the roles of the target file;
every other name reaches the target itself, so tests in the new style (`target.command`, `target.has(...)`) work
on the same object. Capabilities, for code that asks `has_capability("exec")`, are named after the roles they
need. A conftest.py serves it by overriding `target` with the target it wraps:

    import pytest
    import score.itf as itf

    class Box(itf.Facade):
        CAPABILITIES = {"exec": ("command",)}

        def run(self, cmd):
            return self.role("command").exec(cmd)

    @pytest.fixture(scope="session")
    def target(target):
        return Box(target)

Any API can be a facade: the methods, their names and their results are the project's. A facade may also wrap
one device of a multi-device target (`Box(target.gw)`), or hold one facade per device as attributes.
"""


class Facade:
    CAPABILITIES: dict[str, tuple[str, ...]] = {}  # capability name -> the roles it needs

    def __init__(self, handle):
        self.handle = handle

    def __getattr__(self, name):
        """The target's own names (its roles, `has`, `reach`, ...)."""
        if name == "handle" or name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.handle, name)

    def role(self, name: str):
        """The role `name` of the target file; a clear error when the target file has none."""
        if not self.handle.has(name):
            raise NotImplementedError(
                f"{type(self).__name__} needs a {name!r} role, which the target file does not have; "
                f"it has: {', '.join(self.handle.names()) or '(none)'}"
            )
        return self.handle.get(name)

    def capabilities(self) -> set[str]:
        return {name for name, roles in self.CAPABILITIES.items() if all(self.handle.has(r) for r in roles)}

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities()

    def has_all_capabilities(self, capabilities) -> bool:
        return set(capabilities) <= self.capabilities()

    def has_any_capability(self, capabilities) -> bool:
        return bool(set(capabilities) & self.capabilities())

    def get_capabilities(self) -> set[str]:
        return self.capabilities()
