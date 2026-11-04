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
"""The original docker plugin, served by the compatibility layer."""

from score.itf.compat.plugins.docker import docker_configuration, pytest_addoption, pytest_configure, target_init  # noqa: F401
from score.itf.compat.plugins.core import determine_target_scope  # noqa: F401
from score.itf.compat.legacy import DockerTarget  # noqa: F401
from score.itf.packs.docker.process import DockerAsyncProcess  # noqa: F401
from score.itf.compat.target import Target  # noqa: F401
