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
"""ITF's hooks and plugin manager.

The manager recognises `@score.itf.core.hookimpl` and, like the runner-agnostic prototype, also
`@pytest.hookimpl` on an `itf_*` function, so a policy can use either marker.
"""

from __future__ import annotations

import inspect

import pluggy

PROJECT_NAME = "itf"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class ITFHookSpecs:
    @hookspec
    def itf_verify(self, session):
        """Startup checks. Run after bring-up, before the first test."""

    @hookspec
    def itf_teardown(self, session):
        """Session cleanup. Run after the last test, targets still live, before unwind."""


HOOK_NAMES = tuple(n for n in vars(ITFHookSpecs) if n.startswith("itf_"))


class ItfPluginManager(pluggy.PluginManager):
    def __init__(self) -> None:
        super().__init__(PROJECT_NAME)
        self.add_hookspecs(ITFHookSpecs)

    def parse_hookimpl_opts(self, plugin, name):
        opts = super().parse_hookimpl_opts(plugin, name)
        if opts is not None or not name.startswith("itf_"):
            return opts
        method = getattr(plugin, name, None)
        legacy = getattr(method, "pytest_impl", None) if inspect.isroutine(method) else None
        return dict(legacy) if isinstance(legacy, dict) else legacy


def implements_itf_hooks(module) -> bool:
    for name in HOOK_NAMES:
        fn = getattr(module, name, None)
        if inspect.isroutine(fn) and (hasattr(fn, "itf_impl") or hasattr(fn, "pytest_impl")):
            return True
    return False


def new_plugin_manager() -> ItfPluginManager:
    return ItfPluginManager()
