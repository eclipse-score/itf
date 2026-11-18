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
"""Host providers. Constructing the platform creates nothing: `localhost.start` does."""

from collections.abc import Iterator

from score.itf.core import capability

from .command import LocalExec, Platform
from .files import LocalFiles
from .files import Platform as FilesPlatform
from .platform import LocalPlatform, PlatformConfig
from .process import LocalProcess


@capability("platform.instance", label="platform", observes=lambda config: bool(config.get("root")))
def make_platform(config: PlatformConfig) -> Iterator[LocalPlatform]:
    """The config is a dict at run time; its dataclass annotation is the schema. With a `root` a later process
    finds the directory again (a marker file), so the target can be detached and taken down."""
    platform = LocalPlatform(config)
    yield platform
    platform.stop()


@capability("exec.command", label="exec")
def make_exec(platform: Platform) -> LocalExec:
    return LocalExec(platform)


@capability("exec.process", label="process")
def make_process(platform: Platform) -> LocalProcess:
    return LocalProcess(platform)


@capability("files.transfer", label="files")
def make_files(platform: FilesPlatform) -> LocalFiles:
    return LocalFiles(platform)
