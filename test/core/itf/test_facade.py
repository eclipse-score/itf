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
"""Facades: a project's own target API over the roles of a target, without the compatibility layer."""

import pytest

import score.itf as itf


class Command:
    def exec(self, cmd, timeout=30.0):
        return 0, f"ran {cmd}".encode()


class Handle:
    """Stands in for the target handle: roles by name, plus a method of its own."""

    def __init__(self, **roles):
        self.roles = roles

    def has(self, name):
        return name in self.roles

    def names(self):
        return tuple(sorted(self.roles))

    def get(self, name):
        return self.roles[name]

    def reach(self, *states):
        return set(states)

    def __getattr__(self, name):
        try:
            return self.roles[name]
        except KeyError:
            raise AttributeError(name) from None


class Box(itf.Facade):
    CAPABILITIES = {"exec": ("command",), "flash": ("command", "files")}

    def run(self, cmd):
        return self.role("command").exec(cmd)


def test_a_facade_method_uses_the_role_it_names():
    assert Box(Handle(command=Command())).run("ls") == (0, b"ran ls")


def test_a_missing_role_says_which_one_and_what_there_is():
    with pytest.raises(NotImplementedError, match="needs a 'command' role.*it has: files"):
        Box(Handle(files=object())).run("ls")


def test_capabilities_follow_from_the_roles_present():
    box = Box(Handle(command=Command()))
    assert box.get_capabilities() == {"exec"}
    assert box.has_capability("exec") and not box.has_all_capabilities({"exec", "flash"})


def test_every_other_name_is_the_targets():
    box = Box(Handle(command=Command()))
    assert box.command.exec("x") == (0, b"ran x")
    assert box.reach("platform.up") == {"platform.up"}
    with pytest.raises(AttributeError):
        box.nothing
