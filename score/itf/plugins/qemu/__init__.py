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
import logging
import os
import subprocess
import socket
import tempfile
import pytest

from score.itf.plugins.qemu.qemu_target import qemu_target
from score.itf.plugins.qemu.checks import pre_tests_phase
from score.itf.core.utils import padder
from score.itf.core.utils.bunch import Bunch
from score.itf.plugins.qemu.config import load_configuration

logger = logging.getLogger(__name__)


def _get_image_format(path_to_image: str) -> str:
    """Determine the disk image format based on the file extension."""
    image_lower = path_to_image.lower()
    if image_lower.endswith(".wic") or image_lower.endswith(".img"):
        return "raw"
    return "qcow2"


def _create_overlay(base_image: str) -> str:
    """Create a temporary qcow2 overlay backed by *base_image*.

    All writes go to the ephemeral overlay so the original image is never
    modified.  The caller is responsible for cleaning up the returned path.
    """
    overlay_fd, overlay_path = tempfile.mkstemp(suffix=".qcow2", prefix="qemu_overlay_")
    os.close(overlay_fd)
    subprocess.run(
        [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            "-b",
            base_image,
            "-F",
            _get_image_format(base_image),
            overlay_path,
        ],
        check=True,
        capture_output=True,
    )
    logger.info(f"Created qcow2 overlay: {overlay_path} (backing: {base_image})")
    return overlay_path


def pytest_addoption(parser):
    parser.addoption(
        "--qemu-config",
        action="store",
        required=True,
        help="Path to json file with target configurations.",
    )
    parser.addoption(
        "--qemu-image",
        action="store",
        default=None,
        help="Path to a QEMU kernel image",
    )
    parser.addoption(
        "--qemu-disk-image",
        action="store",
        default=None,
        help="Path to a QEMU disk image (qcow2, wic, or img). "
        "An ephemeral overlay is created so the original image is not modified.",
    )
    parser.addoption(
        "--qemu-architecture",
        action="store",
        choices=("x86_64", "aarch64"),
        default="x86_64",
        help="Target CPU architecture used to select the QEMU binary and CPU model.",
    )
    parser.addoption(
        "--qemu-kernel-cmdline-file",
        action="store",
        default=None,
        help="Path to a file containing the Linux kernel command line.",
    )


@pytest.fixture(scope="session")
def dlt():
    """Overrideable fixture for enabling dlt collection.
    The DLT plugin should be loaded after the base plugin.
    """
    pass


@pytest.fixture(scope="session")
def config(request):
    qemu_kernel_cmdline = None
    kernel_cmdline_file = request.config.getoption("qemu_kernel_cmdline_file")
    if kernel_cmdline_file:
        with open(os.path.abspath(kernel_cmdline_file), encoding="utf-8") as handle:
            qemu_kernel_cmdline = handle.read().strip()

    return Bunch(
        qemu_config=load_configuration(request.config.getoption("qemu_config")),
        qemu_image=request.config.getoption("qemu_image"),
        qemu_disk_image=request.config.getoption("qemu_disk_image"),
        qemu_architecture=request.config.getoption("qemu_architecture"),
        qemu_kernel_cmdline=qemu_kernel_cmdline,
    )


@pytest.fixture(scope="session")
def target_init(config, request, dlt):
    logger.info(f"Starting tests on host: {socket.gethostname()}")
    overlay_path = None
    if config.qemu_disk_image:
        overlay_path = _create_overlay(os.path.abspath(config.qemu_disk_image))
    try:
        with qemu_target(
            Bunch(
                qemu_config=config.qemu_config,
                qemu_image=config.qemu_image,
                qemu_disk_image=overlay_path,
                qemu_architecture=config.qemu_architecture,
                qemu_kernel_cmdline=config.qemu_kernel_cmdline,
            )
        ) as qemu:
            pre_tests_phase(qemu)
            yield qemu
    finally:
        if overlay_path and os.path.exists(overlay_path):
            os.unlink(overlay_path)
