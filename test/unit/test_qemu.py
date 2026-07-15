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

from types import SimpleNamespace

import pytest

from score.itf.plugins.qemu.qemu import Qemu


def _build_qemu(
    mocker,
    *,
    machine="pc-x86_64",
    path_to_kernel_image=None,
    kernel_cmdline=None,
    rootfs=None,
    network_adapters=None,
    port_forwarding=None,
):
    if network_adapters is None:
        network_adapters = []
    if port_forwarding is None:
        port_forwarding = []

    mocker.patch("score.itf.plugins.qemu.qemu.os.path.isfile", return_value=True)

    return Qemu(
        path_to_kernel_image=path_to_kernel_image,
        ram="1G",
        cores=2,
        machine=machine,
        network_adapters=network_adapters,
        port_forwarding=port_forwarding,
        rootfs=rootfs,
        kernel_cmdline=kernel_cmdline,
    )


def test_invalid_machine_is_rejected(mocker):
    mocker.patch("score.itf.plugins.qemu.qemu.os.path.isfile", return_value=True)
    with pytest.raises(ValueError):
        Qemu(
            path_to_kernel_image=None,
            ram="1G",
            cores=2,
            machine="invalid-machine",
            network_adapters=[],
            port_forwarding=[],
            rootfs=None,
            kernel_cmdline=None,
        )


@pytest.mark.parametrize(
    "machine,expected_machine_arg,expected_cpu",
    [
        ("pc-x86_64", "pc", "Cascadelake-Server-v5"),
        ("virt-aarch64", "virt,virtualization=true,gic-version=3", "cortex-a53"),
    ],
)
def test_machine_mapping_is_reflected_in_command(mocker, machine, expected_machine_arg, expected_cpu):
    qemu = _build_qemu(mocker, machine=machine)
    command = qemu._Qemu__build_qemu_command()

    machine_idx = command.index("-machine")
    cpu_idx = command.index("-cpu")

    assert command[machine_idx + 1] == expected_machine_arg
    assert command[cpu_idx + 1] == expected_cpu


def test_kernel_args_include_kernel_and_append(mocker):
    qemu = _build_qemu(
        mocker,
        path_to_kernel_image="/tmp/bzImage",
        kernel_cmdline="root=/dev/vda1 rw",
    )

    assert qemu._Qemu__kernel_args() == ["-kernel", "/tmp/bzImage", "-append", "root=/dev/vda1 rw"]


def test_kernel_args_are_empty_without_kernel_image(mocker):
    qemu = _build_qemu(mocker, kernel_cmdline="root=/dev/vda1 rw")

    assert qemu._Qemu__kernel_args() == []


def test_rootfs_args_include_arch_specific_block_device(mocker):
    qemu = _build_qemu(mocker, machine="virt-aarch64", rootfs="/tmp/rootfs.qcow2")

    assert qemu._Qemu__rootfs_args() == [
        "-device",
        "virtio-blk-device,drive=vd0",
        "-drive",
        "if=none,format=qcow2,file=/tmp/rootfs.qcow2,id=vd0",
    ]


def test_rootfs_args_are_empty_without_rootfs(mocker):
    qemu = _build_qemu(mocker)

    assert qemu._Qemu__rootfs_args() == []


def test_network_args_skip_loopback_and_use_machine_specific_device(mocker):
    qemu = _build_qemu(mocker, machine="virt-aarch64", network_adapters=["lo", "tap0"])

    assert qemu._Qemu__network_devices_args() == [
        "-netdev",
        "tap,id=t2,ifname=tap0,script=no,downscript=no",
        "-device",
        "virtio-net-device,netdev=t2,id=nic2,guest_csum=off",
    ]


def test_port_forwarding_args_are_built_from_forwarding_entries(mocker):
    qemu = _build_qemu(
        mocker,
        port_forwarding=[SimpleNamespace(host_port=2222, guest_port=22)],
    )

    assert qemu._Qemu__port_forwarding_args() == [
        "-netdev",
        "user,id=net1,hostfwd=tcp::2222-:22",
        "-device",
        "virtio-net-pci,netdev=net1",
    ]
