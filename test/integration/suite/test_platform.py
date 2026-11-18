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
"""Any target on a platform that can restart; state changes go through the planner."""

from typing import Protocol

import score.itf as itf


class Restart(Protocol):
    __contract__ = "platform.instance"

    def restart(self) -> None: ...


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


itf_requires = [
    itf.requires("platform", contract="platform.instance"),
    itf.requires("command", shape=Command),
]


@itf.requires("platform", shape=Restart)
def test_after_a_restart_reach_brings_every_goal_back(target):
    target.platform.restart()
    target.reach()  # re-plans every goal from what the probes now observe
    assert target.command.exec("echo -n back") == (0, b"back")


def test_renew_gives_a_new_platform_and_reaches_the_goals_again(target):
    old = target.platform
    target.renew("platform")
    assert target.platform is not old
    assert target.command.exec("echo -n renewed") == (0, b"renewed")
