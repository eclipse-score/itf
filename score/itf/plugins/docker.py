# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
import logging
import subprocess
import docker as pypi_docker
import pytest

from score.itf.plugins.core import determine_target_scope
from score.itf.plugins.core import Target


logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--docker-image",
        action="store",
        required=True,
        help="Docker image to run tests against.",
    )
    parser.addoption(
        "--docker-image-bootstrap",
        action="store",
        required=False,
        help="Docker image bootstrap command, that will be executed before referencing the container.",
    )


DOCKER_CAPABILITIES = ["exec"]


class DockerTarget(Target):
    def __init__(self, container, capabilities=DOCKER_CAPABILITIES):
        super().__init__(capabilities=capabilities)
        self.container = container

    def __getattr__(self, name):
        return getattr(self.container, name)


@pytest.fixture(scope=determine_target_scope)
def target_init(request):
    docker_image_bootstrap = request.config.getoption("docker_image_bootstrap")
    if docker_image_bootstrap:
        logger.info(f"Executing custom image bootstrap command: {docker_image_bootstrap}")
        subprocess.run([docker_image_bootstrap], check=True)

    docker_image = request.config.getoption("docker_image")
    client = pypi_docker.from_env()
    container = client.containers.run(docker_image, "sleep infinity", detach=True, auto_remove=True, init=True)
    yield DockerTarget(container)
    container.stop(timeout=1)
