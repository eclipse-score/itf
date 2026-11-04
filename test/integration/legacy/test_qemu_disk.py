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
"""Verifies that a second disk, passed to the QEMU plugin via ``--qemu-disk``,
shows up in the guest, can be mounted and contains the expected content.
"""

EXPECTED_DISK_CONTENT = "Hello from the QEMU disk image!\n"

# The additional disk is attached as the second virtio block device. The
# rootfs occupies the first one, so the disk always shows up as /dev/vdb.
DISK_DEVICE = "/dev/vdb"
MOUNT_POINT = "/mnt/qemu_disk"


def test_disk_device_is_visible(target):
    exit_code, _ = target.execute(f"test -b {DISK_DEVICE}")
    assert exit_code == 0, f"Expected block device {DISK_DEVICE} to be present"


def test_disk_can_be_mounted_and_has_expected_content(target):
    exit_code, _ = target.execute(f"mkdir -p {MOUNT_POINT} && mount {DISK_DEVICE} {MOUNT_POINT}")
    assert exit_code == 0, "Mounting the additional disk failed"
    try:
        exit_code, output = target.execute(f"cat {MOUNT_POINT}/qemu_disk_content.txt")
        assert exit_code == 0
        assert output.decode("utf-8") == EXPECTED_DISK_CONTENT
    finally:
        target.execute(f"umount {MOUNT_POINT}")


def test_disk_is_writable(target):
    exit_code, _ = target.execute(f"mkdir -p {MOUNT_POINT} && mount {DISK_DEVICE} {MOUNT_POINT}")
    assert exit_code == 0, "Mounting the additional disk failed"
    try:
        exit_code, _ = target.execute(f"touch {MOUNT_POINT}/should_be_writable")
        assert exit_code == 0, "Writing to the disk should work"
    finally:
        target.execute(f"umount {MOUNT_POINT}")
