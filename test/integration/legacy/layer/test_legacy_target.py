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
"""The compatibility layer's original target is a facade over the roles, with the original capabilities."""

import pytest

from score.itf.compat.legacy import LegacyTarget


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


def test_the_original_target_is_a_facade_with_the_original_capabilities():
    target = LegacyTarget(Handle(command=Command(), files=object()))
    assert target.execute("ls") == (0, b"ran ls")
    assert target.get_capabilities() == {"exec", "file_transfer"}
    with pytest.raises(NotImplementedError, match="'platform' role"):
        target.restart()


class Platform:
    def running(self):
        return True


class Session:
    """Stands in for the session the compatibility policy's itf_verify gets: a target and check()."""

    def __init__(self, target):
        self.target, self.checks = target, {}

    def check(self, name, ok, detail=""):
        self.checks[name] = ok


def test_the_compatibility_policy_checks_the_command_answers_with_bytes():
    # The QEMU compatibility targets run this check at startup; command.exec returns bytes.
    import importlib.util
    from pathlib import Path

    import score.itf.compat

    path = Path(score.itf.compat.__file__).parent / "targets" / "policy.py"
    spec = importlib.util.spec_from_file_location("compat_policy_under_test", path)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)

    class Ready:
        def exec(self, cmd, timeout=30.0):
            return 0, b"ready"

    session = Session(Handle(command=Ready(), platform=Platform()))
    session.target.names = lambda: ("command", "platform")
    policy.itf_verify(session)
    assert session.checks == {"command.answers": True}
