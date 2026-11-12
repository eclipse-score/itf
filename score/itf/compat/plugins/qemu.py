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
"""The original qemu plugin: its options, the overridable `dlt` fixture and a `target_init` serving a
`QemuTarget`. `--qemu-config` selects the qemu target file shipped in `targets/` (`qemu_dlt` with the dlt plugin),
unless `--itf-target` names the project's own."""

import os

import pytest

from ..legacy import QemuTarget
from .core import itf_session, option
from .targets import select


def pytest_addoption(parser):
    group = parser.getgroup("itf qemu")
    group.addoption(
        "--qemu-boot-attempts",
        type=int,
        default=3,
        help="Maximum number of times the guest is booted if its kernel panics during boot.",
    )
    group.addoption("--qemu-config", help="Path to json file with target configurations.")
    group.addoption("--qemu-kernel", help="Path to a QEMU kernel image.")
    group.addoption("--qemu-image", help="[DEPRECATED] Alias for --qemu-kernel.")
    group.addoption("--qemu-rootfs", help="Path to a QEMU disk image, booted through a temporary overlay.")
    group.addoption("--qemu-disk", help="Path to an additional disk image.")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if not option(config, "qemu_config"):
        return
    if option(config, "qemu_image"):
        config.issue_config_time_warning(
            DeprecationWarning(
                "--qemu-image is deprecated and will be removed in a future release. Please use --qemu-kernel instead."
            ),
            stacklevel=2,
        )
    paths = {
        "LEGACY_QEMU_CONFIG": option(config, "qemu_config"),
        "LEGACY_QEMU_KERNEL": option(config, "qemu_kernel") or option(config, "qemu_image"),
        "LEGACY_QEMU_ROOTFS": option(config, "qemu_rootfs"),
        "LEGACY_QEMU_DISK": option(config, "qemu_disk"),
    }
    select(config, "qemu", {k: os.path.abspath(v) for k, v in paths.items() if v})
    # A guest that panics while booting stops QEMU (the qemu pack watches its console), so platform.up stops holding
    # and the session plans the boot again: the original plugin's boot attempts are the session's bring-up attempts.
    config.option.itf_bring_up_attempts = max(config.option.itf_bring_up_attempts, option(config, "qemu_boot_attempts"))


@pytest.fixture(scope="session")
def dlt():
    """Overrideable fixture for enabling dlt collection (the dlt plugin records the session's DLT)."""
    yield None


@pytest.fixture(scope="session")
def target_init(request, dlt):
    session = itf_session(request.config)
    if session is None:
        raise pytest.UsageError("the qemu plugin needs --qemu-config (or --itf-target)")
    yield QemuTarget(session.target)
