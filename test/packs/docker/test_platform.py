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
"""The docker platform without a daemon: what it refuses before it asks one for anything."""

import pytest

from score.itf.packs.docker import exec_client
from score.itf.packs.docker.platform import DockerPlatform


def test_a_volume_whose_host_path_is_missing_is_refused_before_the_daemon_is_asked(tmp_path, monkeypatch):
    # A rootful daemon would create the missing path itself, owned by root, where nothing can clean it up.
    platform = DockerPlatform({"image": "ubuntu:24.04", "volumes": f"{tmp_path / 'nowhere'}:/mnt:ro"})
    monkeypatch.setattr(platform, "client", lambda: pytest.fail("the daemon must not be asked"))
    with pytest.raises(FileNotFoundError, match="nowhere"):
        platform.start()


def test_volumes_that_exist_are_passed_on(tmp_path):
    platform = DockerPlatform({"image": "ubuntu:24.04", "volumes": f"{tmp_path}:/mnt:ro"})
    assert platform.volumes == {str(tmp_path): {"bind": "/mnt", "mode": "ro"}}


def test_no_container_engine_is_reported_with_how_to_start_one(monkeypatch):
    docker_sdk = pytest.importorskip("docker")

    def refuse(**_):
        raise docker_sdk.errors.DockerException("Error while fetching server API version")

    # the client the platform makes (exec_client.from_env), refused as the SDK refuses when no engine answers
    monkeypatch.setattr(exec_client, "from_env", refuse)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    with pytest.raises(ConnectionError, match="DOCKER_HOST is not set.*podman.socket"):
        DockerPlatform({"image": "ubuntu:24.04"}).client()


class Container:
    def __init__(self, refusals):
        self.refusals, self.name, self.stopped, self.removed = refusals, "score_itf_x", False, False

    def stop(self, timeout):
        self.stopped = True

    def remove(self, force):
        if self.refusals:
            self.refusals -= 1
            raise RuntimeError("removal of container score_itf_x is already in progress")
        self.removed = True


def test_a_removal_refused_right_after_the_stop_is_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    platform = DockerPlatform({"image": "ubuntu:24.04", "isolated_network": False})
    platform.container = container = Container(refusals=2)
    platform.stop()
    assert container.stopped and container.removed and platform.container is None
