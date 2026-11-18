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
"""In-memory platform providers, for offline runs."""

from collections.abc import Iterator

from score.itf.core import capability

from .platform import Platform, PlatformConfig, SimExec, SimPlatform


@capability("platform.instance", label="platform", observes=lambda config: bool(config.get("state_dir")))
def make_platform(config: PlatformConfig) -> Iterator[SimPlatform]:
    """With a `state_dir` a later process sees that the platform is up and can take it down."""
    platform = SimPlatform(config["name"], config.get("ip", "127.0.0.1"), config.get("state_dir"))
    yield platform
    platform.stop()


@capability("exec.command", label="exec")
def make_exec(platform: Platform) -> SimExec:
    return SimExec(platform)
