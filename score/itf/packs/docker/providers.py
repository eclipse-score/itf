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
"""Docker providers. Constructing the platform starts nothing: `docker.start` (steps.py) does;
teardown stops and removes the container and the network created for it."""

from collections.abc import Iterator

from score.itf.core import capability

from .command import DockerExec, Platform
from .endpoint import DockerEndpoint, EndpointConfig, EndpointPlatform
from .files import DockerFiles
from .platform import DockerPlatform, PlatformConfig
from .process import DockerProcess


@capability("platform.instance", label="platform")
def make_platform(config: PlatformConfig) -> Iterator[DockerPlatform]:
    platform = DockerPlatform(config)
    yield platform
    platform.stop()


@capability("exec.command", label="exec")
def make_exec(platform: Platform) -> DockerExec:
    return DockerExec(platform)


@capability("exec.process", label="process")
def make_process(platform: Platform) -> DockerProcess:
    return DockerProcess(platform)


@capability("files.transfer", label="files")
def make_files(platform: Platform) -> DockerFiles:
    return DockerFiles(platform)


@capability("descriptor.endpoint", label="endpoint")
def make_endpoint(platform: EndpointPlatform, config: EndpointConfig) -> DockerEndpoint:
    return DockerEndpoint(platform, config)
