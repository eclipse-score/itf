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
"""Virtual machines booted with a second disk (the `platform` option `disk`): it shows up as /dev/vdb."""

from uuid import uuid4

import pytest

import score.itf as itf

MOUNT = "/mnt/qemu_disk"


@itf.requires("platform", shape=["disk"])
@itf.requires("command")
def test_the_second_disk_mounts_with_expected_content_and_is_writable(target):
    if not target.platform.disk:
        pytest.skip("the target file boots no second disk")
    assert target.command.exec("test -b /dev/vdb")[0] == 0, "expected block device /dev/vdb"
    assert target.command.exec(f"mkdir -p {MOUNT} && mount /dev/vdb {MOUNT}")[0] == 0
    try:
        assert target.command.exec(f"cat {MOUNT}/qemu_disk_content.txt") == (0, b"Hello from the QEMU disk image!\n")
        assert target.command.exec(f"touch {MOUNT}/should_be_writable")[0] == 0
    finally:
        target.command.exec(f"umount {MOUNT}")


@itf.requires("platform", shape=["disk"])
@itf.requires("command")
def test_guest_written_second_disk_data_survives_qemu_restart(target):
    if not target.platform.disk:
        pytest.skip("the target file boots no second disk")
    marker = f"{MOUNT}/persist-{uuid4().hex}"
    value = f"survives-{uuid4().hex}"
    assert target.command.exec(f"mkdir -p {MOUNT} && mount /dev/vdb {MOUNT}")[0] == 0
    try:
        assert target.command.exec(f"printf '%s' '{value}' > '{marker}'")[0] == 0
    finally:
        assert target.command.exec(f"umount {MOUNT}")[0] == 0

    target.platform.restart()
    target.reach()

    code, output = target.command.exec(f"mkdir -p {MOUNT} && mount /dev/vdb {MOUNT}")
    assert code == 0, output.decode(errors="replace")
    try:
        assert target.command.exec(f"cat '{marker}'") == (0, value.encode())
    finally:
        assert target.command.exec(f"rm -f '{marker}' && umount {MOUNT}")[0] == 0
