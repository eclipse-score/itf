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

import pytest

from score.itf.plugins.qemu.config import QemuConfigModel


_VALID_BRIDGE_CONFIG = {
    "networks": [{"name": "tap0", "ip_address": "169.254.158.190", "gateway": "169.254.21.88"}],
    "ssh_port": 22,
    "qemu_num_cores": 2,
    "qemu_ram_size": "1G",
}

_VALID_PORT_FORWARDING_CONFIG = {
    "networks": [{"name": "lo", "ip_address": "127.0.0.1", "gateway": "127.0.0.1"}],
    "ssh_port": 2222,
    "qemu_num_cores": 2,
    "qemu_ram_size": "1G",
    "port_forwarding": [{"host_port": 2222, "guest_port": 22}],
}


def test_valid_bridge_config():
    QemuConfigModel.model_validate(_VALID_BRIDGE_CONFIG)


def test_valid_port_forwarding_config():
    QemuConfigModel.model_validate(_VALID_PORT_FORWARDING_CONFIG)


@pytest.mark.parametrize("machine", ["pc-x86_64", "virt-aarch64"])
def test_valid_qemu_machine_values(machine):
    config = {**_VALID_BRIDGE_CONFIG, "qemu_machine": machine}
    model = QemuConfigModel.model_validate(config)
    assert model.qemu_machine == machine


def test_default_qemu_machine_value_is_applied():
    model = QemuConfigModel.model_validate(_VALID_BRIDGE_CONFIG)
    assert model.qemu_machine == "pc-x86_64"


def test_invalid_qemu_machine_value_is_rejected():
    config = {**_VALID_BRIDGE_CONFIG, "qemu_machine": "virt-riscv64"}
    with pytest.raises(Exception):
        QemuConfigModel.model_validate(config)


def test_qemu_kernel_cmdline_is_accepted():
    cmdline = "root=/dev/vda1 rw console=ttyS0"
    config = {**_VALID_BRIDGE_CONFIG, "qemu_kernel_cmdline": cmdline}
    model = QemuConfigModel.model_validate(config)
    assert model.qemu_kernel_cmdline == cmdline


def test_missing_networks_is_rejected():
    config = {**_VALID_BRIDGE_CONFIG}
    del config["networks"]
    with pytest.raises(Exception):
        QemuConfigModel.model_validate(config)


def test_empty_networks_is_rejected():
    config = {**_VALID_BRIDGE_CONFIG, "networks": []}
    with pytest.raises(Exception):
        QemuConfigModel.model_validate(config)


def test_invalid_ip_address_is_rejected():
    config = {
        **_VALID_BRIDGE_CONFIG,
        "networks": [{"name": "tap0", "ip_address": "not-an-ip", "gateway": "169.254.21.88"}],
    }
    with pytest.raises(Exception):
        QemuConfigModel.model_validate(config)


def test_invalid_ssh_port_is_rejected():
    config = {**_VALID_BRIDGE_CONFIG, "ssh_port": 0}
    with pytest.raises(Exception):
        QemuConfigModel.model_validate(config)


def test_invalid_ram_size_is_rejected():
    config = {**_VALID_BRIDGE_CONFIG, "qemu_ram_size": "1GB"}
    with pytest.raises(Exception):
        QemuConfigModel.model_validate(config)


def test_unknown_keys_are_rejected():
    config = {**_VALID_BRIDGE_CONFIG, "unknown_key": "value"}
    with pytest.raises(Exception):
        QemuConfigModel.model_validate(config)
