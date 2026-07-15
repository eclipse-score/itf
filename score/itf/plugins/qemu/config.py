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
"""QEMU plugin configuration loading and validation.

The QEMU pytest plugin expects a JSON configuration file passed via the
`--qemu-config` command line option. The configuration is validated using
Pydantic (unknown keys are rejected) and returned as a Pydantic model.

The allowed configuration format is based on the JSON files in
`test/resources/qemu_*_config.json`.

Required top-level keys:
    - `networks` (array, at least 1 item)
    - `ssh_port` (int 1..65535)
    - `qemu_num_cores` (int >= 1)
    - `qemu_ram_size` (string like "512M" or "1G")

Optional top-level keys:
        - `qemu_machine` (`pc-x86_64` or `virt-aarch64`, default `pc-x86_64`)
        - `qemu_kernel_cmdline` (string)
    - `port_forwarding` (array of objects with `host_port` and `guest_port`)

Each entry in `networks` must contain:
    - `name` (string)
    - `ip_address` (IPv4 string)
    - `gateway` (IPv4 string)

Example: bridge/tap networking

        {
            "networks": [
                {
                    "name": "tap0",
                    "ip_address": "169.254.158.190",
                    "gateway": "169.254.21.88"
                }
            ],
            "ssh_port": 22,
            "qemu_num_cores": 2,
            "qemu_ram_size": "1G",
            "qemu_machine": "virt-aarch64",
            "qemu_kernel_cmdline": "root=/dev/vda1 sdk_enable lisa_syscall_whitelist=2026 rw sharedmem.enable_sharedmem=0 init=/usr/bin/ebclfsa-cflinit"
        }

Example: port-forwarding networking

        {
            "networks": [
                {
                    "name": "lo",
                    "ip_address": "127.0.0.1",
                    "gateway": "127.0.0.1"
                }
            ],
            "ssh_port": 2222,
            "qemu_num_cores": 2,
            "qemu_ram_size": "1G",
            "port_forwarding": [
                {
                    "host_port": 2222,
                    "guest_port": 22
                }
            ]
        }
"""

import json
import logging
import ipaddress
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


logger = logging.getLogger(__name__)


_RAM_SIZE_PATTERN = r"^[0-9]+[KMGTP]$"


class Network(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    ip_address: str
    gateway: str

    @field_validator("ip_address", "gateway")
    @classmethod
    def _validate_ipv4(cls, value: str) -> str:
        try:
            ip = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("must be a valid IPv4 address") from exc
        if ip.version != 4:
            raise ValueError("must be a valid IPv4 address")
        return value


class PortForwarding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host_port: int = Field(ge=1, le=65535)
    guest_port: int = Field(ge=1, le=65535)


class QemuConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    networks: list[Network] = Field(min_length=1)
    ssh_port: int = Field(ge=1, le=65535)
    qemu_num_cores: int = Field(ge=1)
    qemu_ram_size: str = Field(pattern=_RAM_SIZE_PATTERN)
    qemu_machine: Literal["pc-x86_64", "virt-aarch64"] = "pc-x86_64"
    qemu_kernel_cmdline: str | None = None
    port_forwarding: list[PortForwarding] = Field(default_factory=list)


def load_configuration(config_file: str) -> QemuConfigModel:
    """Load and validate a QEMU configuration file.

    Args:
        config_file: Path to a JSON configuration file.

    Returns:
        A validated Pydantic model.

    Raises:
        ValueError: If validation fails.
    """
    logger.info(f"Loading configuration from {config_file}")

    with open(config_file, "r") as f:
        config_data = json.load(f)

    try:
        return QemuConfigModel.model_validate(config_data)
    except ValidationError as exc:
        prefix = f"Invalid QEMU configuration in '{config_file}'"
        raise ValueError(prefix + f": {exc}") from exc
