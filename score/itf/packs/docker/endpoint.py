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
"""A service in the container as an endpoint (`docker.endpoint`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EndpointConfig:
    port: int = 22
    protocol: str = "tcp"
    via: str = "auto"


class EndpointPlatform(Protocol):
    __contract__ = "platform.instance"

    def ip(self, network: str | None = None) -> str: ...
    def host_port(self, container_port: str) -> int | None: ...


class DockerEndpoint:
    """`endpoint` for a service in the container, read when used (the
    container's address exists only once it runs). `via`: "ip" (the container's own address),
    "published" (127.0.0.1 and the published host port; needed with rootless Podman), or "auto"
    (published when the port is published, else ip)."""

    host: str  # properties below; declared here so the class names its shape
    port: int

    def __init__(self, platform: EndpointPlatform, config: dict):
        self.platform = platform
        self.container_port = config.get("port", 22)
        self.key = f"{self.container_port}/{config.get('protocol', 'tcp')}"
        self.via = config.get("via", "auto")
        if self.via not in ("auto", "ip", "published"):
            raise ValueError(f"via must be auto, ip or published, not {self.via!r}")

    def _published(self) -> int | None:
        return None if self.via == "ip" else self.platform.host_port(self.key)

    @property
    def host(self) -> str:
        if self._published() is not None:
            return "127.0.0.1"
        if self.via == "published":
            raise RuntimeError(f"container port {self.key} is not published")
        return self.platform.ip()

    @property
    def port(self) -> int:
        return self._published() or self.container_port
