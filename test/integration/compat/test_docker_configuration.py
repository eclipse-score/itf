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
"""The original Docker API through the original plugin: keys of the docker_configuration fixture that the typed
settings do not name reach the Docker SDK, as the original plugin passed them to containers.run, and so do the
arguments given explicitly as docker_sdk_kwargs."""

import pytest


@pytest.fixture(scope="session")
def docker_configuration():
    return {"mem_limit": "256m", "docker_sdk_kwargs": {"labels": {"itf.sdk-kwargs": "enabled"}}}


def test_extra_sdk_kwargs_reach_the_container(target):
    target.container.reload()
    assert target.container.attrs["HostConfig"]["Memory"] == 256 * 1024 * 1024
    assert target.container.labels["itf.sdk-kwargs"] == "enabled"
