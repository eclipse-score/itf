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
``--qemu-config`` command line option.  The JSON must contain a top-level
``qemu`` key whose value is validated using Pydantic (unknown keys are
rejected) and returned as a :class:`QemuConfigModel`.

Example::

    {
        "qemu": {
            "ram_size": 1024,
            "cpu_count": 2,
            "enable_kvm": true,
            "kernel_rootfs_folder": "_sys/",
            "disk_image": "./disk-score.qcow2",
            "startup_timeout": 60,
            "logfile": "_test_results/sys4/qemu.log",
            "security_enabled": false,
            "host_qemu_network": {
                "subnet": "192.168.120.0/24",
                "ip_address": "192.168.120.20",
                "mac_address": "52:54:00:12:34:72",
                "port_forwarding": [
                    {
                        "description": "SSH",
                        "host_port": 2210,
                        "target_port": 22
                    }
                ]
            },
            "qemu_network": {
                "ip_address": "192.168.116.20",
                "mcast_socket_port": 5432,
                "mcast_socket_mac": "52:54:00:12:34:74"
            }
        }
    }
"""

import json
import logging
import ipaddress
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)


class PortForwarding(BaseModel):
    """A single port-forwarding rule inside ``host_qemu_network``."""

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    host_port: int = Field(ge=1, le=65535)
    target_port: int = Field(ge=1, le=65535)


class HostQemuNetwork(BaseModel):
    """Network configuration between the host and the QEMU guest.

    Supports both the new format (``subnet``, ``ip_address``) and the legacy
    format (``subnet_address``, ``machine_address``).  When legacy fields are
    provided they are automatically converted to the new ones.
    """

    model_config = ConfigDict(extra="forbid")

    subnet: str = Field(default="", min_length=0)
    ip_address: str = Field(default="", min_length=0)
    mac_address: str = Field(min_length=1)
    port_forwarding: List[PortForwarding] = Field(default_factory=list)

    # Legacy fields (optional, converted in the model validator below)
    subnet_address: Optional[str] = Field(default=None, exclude=True)
    machine_address: Optional[str] = Field(default=None, exclude=True)
    network_adapter: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _migrate_legacy_fields(self) -> "HostQemuNetwork":
        """Convert legacy ``subnet_address``/``machine_address`` to ``subnet``/``ip_address``."""
        if self.subnet_address is not None and not self.subnet:
            # Build a /24 subnet from the legacy three-octet prefix
            self.subnet = f"{self.subnet_address}.0/24"
        if self.machine_address is not None and not self.ip_address:
            prefix = self.subnet_address or ""
            self.ip_address = f"{prefix}{self.machine_address}"
        if not self.subnet:
            raise ValueError("Either 'subnet' or legacy 'subnet_address' must be provided")
        if not self.ip_address:
            raise ValueError("Either 'ip_address' or legacy 'subnet_address'+'machine_address' must be provided")
        return self


class QemuNetwork(BaseModel):
    """Optional inter-QEMU multicast network configuration."""

    model_config = ConfigDict(extra="forbid")

    ip_address: str
    mcast_socket_port: int = Field(ge=1, le=65535)
    mcast_socket_mac: str = Field(min_length=1)

    @field_validator("ip_address")
    @classmethod
    def _validate_ipv4(cls, value: str) -> str:
        try:
            ip = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("must be a valid IPv4 address") from exc
        if ip.version != 4:
            raise ValueError("must be a valid IPv4 address")
        return value


class QemuConfigModel(BaseModel):
    """Validated QEMU configuration."""

    model_config = ConfigDict(extra="forbid")

    ram_size: int = Field(ge=1, description="RAM in MB")
    cpu_count: int = Field(ge=1)
    enable_kvm: bool = True
    kernel_rootfs_folder: str = ""
    disk_image: str = ""
    startup_timeout: int = Field(ge=0, default=60)
    logfile: str = ""
    security_enabled: bool = False

    host_qemu_network: HostQemuNetwork
    qemu_network: Optional[QemuNetwork] = None

    @field_validator("qemu_network", mode="before")
    @classmethod
    def _normalize_empty_qemu_network(cls, v: object) -> object:
        if isinstance(v, dict) and not v:
            return None
        return v

    # ----- computed helpers (read-only properties) -----

    @property
    def ip_address(self) -> str:
        """Host-reachable IP for connecting to the QEMU guest.

        Returns ``127.0.0.1`` when port forwarding is configured (user-mode
        networking), otherwise the guest IP directly.
        """
        if self.host_qemu_network.port_forwarding:
            return "127.0.0.1"
        return self.host_qemu_network.ip_address

    @property
    def ssh_port(self) -> int:
        """Derive the SSH port from the port-forwarding entry with ``target_port == 22``.

        Falls back to port 22 if no matching entry is found.
        """
        for pf in self.host_qemu_network.port_forwarding:
            if pf.target_port == 22:
                return pf.host_port
        return 22


def load_configuration(config_file: str) -> QemuConfigModel:
    """Load and validate a QEMU configuration file.

    The JSON file must contain a top-level ``"qemu"`` key.

    Args:
        config_file: Path to a JSON configuration file.

    Returns:
        A validated :class:`QemuConfigModel`.

    Raises:
        ValueError: If the file is missing the ``qemu`` key or validation fails.
    """
    logger.info(f"Loading configuration from {config_file}")

    with open(config_file, "r") as f:
        raw = json.load(f)

    if "qemu" not in raw:
        raise ValueError(f"Invalid QEMU configuration in '{config_file}': missing top-level 'qemu' key")

    try:
        return QemuConfigModel.model_validate(raw["qemu"])
    except ValidationError as exc:
        prefix = f"Invalid QEMU configuration in '{config_file}'"
        raise ValueError(prefix + f": {exc}") from exc
