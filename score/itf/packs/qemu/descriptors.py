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
"""The endpoint and login a QEMU configuration names (`qemu.endpoint`, `qemu.credentials`)."""

from __future__ import annotations

from typing import Protocol

from .config import QemuConfigModel


class ConfiguredPlatform(Protocol):
    __contract__ = "platform.instance"

    qemu_config: QemuConfigModel


class QemuEndpoint:
    """The SSH endpoint the QEMU configuration names: the first network's address and `ssh_port`."""

    host: str
    port: int

    def __init__(self, platform: ConfiguredPlatform):
        self.host = platform.qemu_config.networks[0].ip_address
        self.port = platform.qemu_config.ssh_port


class QemuCredentials:
    """The login the configuration's `ssh_auth` names; without one, root with an empty password."""

    user: str
    password: str | None
    key_path: str | None

    def __init__(self, platform: ConfiguredPlatform):
        auth = platform.qemu_config.ssh_auth
        if not auth.username:
            raise ValueError("Missing or invalid SSH username value")
        self.user = auth.username
        self.key_path = auth.pkey_path
        self.password = auth.password if auth.password is not None or auth.pkey_path else ""
