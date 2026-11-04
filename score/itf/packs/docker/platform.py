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
"""The container behind `docker.instance`: start, stop, restart, addresses, coverage."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from score.itf.core.process import ProcessWrapper

from . import exec_client
from .files import download

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformConfig:
    image: str
    name: str | None = None
    command: str | None = "sleep infinity"
    init: bool = True
    shm_size: str | None = "2G"
    privileged: bool = False
    environment: str | None = None
    ports: str | None = None
    volumes: str | None = None
    network: str | None = None
    isolated_network: bool = True
    bootstrap: str | None = None
    extract_coverage: bool = False
    coverage_dir: str | None = None
    client_timeout: int = 180


def parse_ports(spec: str | None) -> dict:
    """ "22/tcp:2222,3490/tcp" -> {"22/tcp": 2222, "3490/tcp": None}; None lets the daemon pick."""
    ports = {}
    for entry in filter(None, (e.strip() for e in (spec or "").split(","))):
        container_port, _, host_port = entry.partition(":")
        ports[container_port] = int(host_port) if host_port else None
    return ports


def parse_volumes(spec: str | None) -> dict:
    """ "/host:/in/container:rw,..." -> {"/host": {"bind": "/in/container", "mode": "rw"}}."""
    volumes = {}
    for entry in filter(None, (e.strip() for e in (spec or "").split(","))):
        host_path, container_path, *mode = entry.split(":")
        volumes[os.path.abspath(host_path)] = {"bind": container_path, "mode": mode[0] if mode else "rw"}
    return volumes


def parse_environment(spec: str | None) -> dict:
    """ "KEY=value,..." -> {"KEY": "value"}."""
    return dict(entry.split("=", 1) for entry in filter(None, (e.strip() for e in (spec or "").split(","))))


class DockerPlatform:
    """`platform`: one container, and its own bridge network unless told otherwise."""

    container: object  # the docker SDK container, once started

    def __init__(self, config: dict):
        self.image = config["image"]
        self.name = config.get("name") or f"score_itf_{os.urandom(6).hex()}"
        self.command = config.get("command", "sleep infinity")
        self.init = config.get("init", True)
        self.shm_size = config.get("shm_size", "2G")
        self.privileged = config.get("privileged", False)
        self.environment = parse_environment(config.get("environment"))
        self.ports = parse_ports(config.get("ports"))
        self.volumes = parse_volumes(config.get("volumes"))
        self.network_name = config.get("network")
        self.isolated_network = config.get("isolated_network", True) and not self.network_name
        self.bootstrap = config.get("bootstrap")
        self.extract_coverage = config.get("extract_coverage", False)
        self.coverage_dir = config.get("coverage_dir") or os.path.join(
            os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "/tmp"), "sysroot"
        )
        self.client_timeout = config.get("client_timeout", 180)
        self._client = None
        self._network = None
        self.container = None

    def client(self):
        if self._client is None:
            import docker as docker_sdk  # loaded when a container is used, never for a plan

            try:
                self._client = exec_client.from_env(timeout=self.client_timeout)  # keeps early exec output
            except docker_sdk.errors.DockerException as exc:
                where = os.environ.get("DOCKER_HOST") or "the default socket (DOCKER_HOST is not set)"
                raise ConnectionError(
                    f"no container engine answers at {where}: {exc}. Start Docker, or for rootless Podman run "
                    "`systemctl --user enable --now podman.socket` and "
                    "`export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`; `itf doctor <target file>` "
                    "checks it (under `bazel test`, pass --test_env=DOCKER_HOST)"
                ) from exc
        return self._client

    def start(self) -> None:
        if self.bootstrap:
            logger.info("Running image bootstrap: %s", self.bootstrap)
            code, _, stderr = ProcessWrapper.run(self.bootstrap)
            if code != 0:
                raise RuntimeError(f"image bootstrap {self.bootstrap} failed ({code}):\n{stderr}")
        missing = sorted(source for source in self.volumes if not os.path.exists(source))
        if missing:
            # A rootful Docker daemon would create them, owned by root, where nothing can clean them up.
            raise FileNotFoundError(f"volumes: the host paths {missing} do not exist; create them, or mount others")
        client = self.client()
        if self.isolated_network:
            # A network of its own, so ip() and gateway() are unique to this container.
            self._network = client.networks.create(f"{self.name}_net", driver="bridge")
            self.network_name = self._network.name
        try:
            self.container = client.containers.run(
                self.image,
                self.command,
                name=self.name,
                detach=True,
                auto_remove=False,
                init=self.init,
                environment=self.environment,
                volumes=self.volumes,
                ports=self.ports,
                shm_size=self.shm_size,
                privileged=self.privileged,
                network=self.network_name,
            )
            logger.info(
                "container %s started from %s (ports %s)", self.container.short_id, self.image, self.ports or "none"
            )
        except Exception:
            self._remove_network()
            raise

    def running(self) -> bool:
        if self.container is None:
            return False
        self.container.reload()
        return self.container.status == "running"

    def restart(self) -> None:
        self.container.restart(timeout=1)

    def stop(self) -> None:
        if self.container is not None:
            if self.extract_coverage:
                try:
                    self._extract_coverage()
                except Exception:
                    logger.warning("Coverage extraction failed", exc_info=True)
            try:
                self.container.stop(timeout=1)
            finally:
                self._remove_container()
                self.container = None
        self._remove_network()

    def _remove_container(self, attempts: int = 5) -> None:
        """Remove the container, retrying: an engine under load can refuse a removal right after a stop, and a
        container left behind outlives the run."""
        for attempt in range(1, attempts + 1):
            try:
                self.container.remove(force=True)
                return
            except Exception as exc:  # noqa: BLE001  the SDK raises several types for the same transient refusal
                if "No such container" in str(exc) or "404" in str(exc):
                    return
                if attempt == attempts:
                    logger.warning("container %s was not removed: %s", self.container.name, exc)
                    raise
                time.sleep(0.5 * attempt)

    def _remove_network(self) -> None:
        if self._network is not None:
            try:
                self._network.remove()
            except Exception:
                logger.warning("Failed to remove network %s", self._network.name, exc_info=True)
            self._network = None

    def exec(self, command: str) -> str:
        """stdout and stderr of `command` run by /bin/sh; raises on a nonzero exit."""
        code, output = self.container.exec_run(["/bin/sh", "-c", command])
        text = output.decode(errors="replace")
        if code != 0:
            raise RuntimeError(f"docker exec failed ({code}): {command}\n{text}")
        return text

    def _network_attr(self, key: str, network: str | None) -> str:
        self.container.reload()
        networks = self.container.attrs["NetworkSettings"]["Networks"]
        network = network or self.network_name
        if network is not None:
            if network not in networks:
                raise RuntimeError(f"container {self.name} is not attached to network {network!r}")
            return networks[network][key]
        value = next((v.get(key) for v in networks.values() if v.get(key)), None)
        if value is None:
            raise RuntimeError(f"container {self.name} has no {key} on any network")
        return value

    def ip(self, network: str | None = None) -> str:
        return self._network_attr("IPAddress", network)

    def gateway(self, network: str | None = None) -> str:
        return self._network_attr("Gateway", network)

    def host_port(self, container_port: str) -> int | None:
        """The host port published for `container_port` ("22/tcp"), or None."""
        self.container.reload()
        bindings = (self.container.attrs["NetworkSettings"].get("Ports") or {}).get(container_port)
        return int(bindings[0]["HostPort"]) if bindings else None

    def _extract_coverage(self) -> None:
        """Download the .gcda files the run created, mirroring their container paths."""
        for change in self.container.diff() or ():
            path = change["Path"]
            if not path.endswith(".gcda") or change["Kind"] not in (0, 1):
                continue
            local = os.path.join(self.coverage_dir, path.lstrip("/"))
            if not os.path.realpath(local).startswith(os.path.realpath(self.coverage_dir)):
                logger.warning("Skipping path traversal attempt: %s", path)
                continue
            try:
                download(self.container, path, local)
            except Exception:
                logger.warning("Failed to extract %s", path, exc_info=True)
