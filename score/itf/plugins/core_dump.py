# *******************************************************************************
# Copyright (c) 2025-2026 Contributors to the Eclipse Foundation
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

import pytest

from score.itf.plugins.core import determine_target_scope

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--extract-core-dumps",
        action="store_true",
        default=False,
        help="Copy core dump files from the target to the host before teardown.",
    )
    parser.addoption(
        "--core-dumps-output-dir",
        default=os.path.join(
            os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "/tmp"),
            "coredumps",
        ),
        help="Directory to write extracted core dump files. "
        "Defaults to $TEST_UNDECLARED_OUTPUTS_DIR/coredumps or /tmp/coredumps.",
    )


def _extract_core_dumps(target, output_base):
    """Extract core dump files from a target via execute and download.

    Searches common core file locations that work on both Linux and QNX guests.

    :param target: Target object providing exec and file_transfer capabilities.
    :param output_base: Local directory where extracted core dump files are stored.
    """
    logger.info(f"Attempting core dump extraction to {output_base}")
    os.makedirs(output_base, exist_ok=True)
    _exit_code, output = target.execute(
        "(ls -1 /core* 2>/dev/null || true)"
        " && (ls -1 /opt/*/core* 2>/dev/null || true)"
        " && (ls -1 /root/core* 2>/dev/null || true)"
        " && (ls -1 /tmp/core* 2>/dev/null || true)"
        " && (ls -1 /data/*/core* 2>/dev/null || true)"
        " && (ls -1 /tmp/*.core /tmp/*.core.gz /var/*.core /var/*.core.gz 2>/dev/null || true)"
        " && (ls -1 /opt/*/*.core /opt/*/*.core.gz /root/*.core /root/*.core.gz"
        " /data/*/*.core /data/*/*.core.gz 2>/dev/null || true)"
    )
    core_dump_paths = [line.strip() for line in output.decode().splitlines() if line.strip()]
    logger.info(f"Found {len(core_dump_paths)} core files: {core_dump_paths}")
    if not core_dump_paths:
        return

    for remote_path in core_dump_paths:
        local_path = os.path.join(output_base, remote_path.lstrip("/"))
        if not os.path.realpath(local_path).startswith(os.path.realpath(output_base)):
            logger.warning(f"Skipping path traversal attempt: {remote_path}")
            continue
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        try:
            logger.info(f"Extracting core dump from {remote_path} to {local_path}")
            target.download(remote_path, local_path)
            logger.info(f"Successfully extracted {remote_path}")
        except Exception:
            logger.warning(f"Failed to extract core dump file {remote_path}", exc_info=True)


@pytest.fixture(scope=determine_target_scope, autouse=True)
def _core_dump_extraction(request, target):
    """Autouse fixture that extracts core dumps after target teardown.

    Activated by --extract-core-dumps. Silently skipped when the target
    does not advertise exec and file_transfer capabilities.
    """
    yield
    if not request.config.getoption("extract_core_dumps"):
        return
    if not target.has_all_capabilities({"exec", "file_transfer"}):
        logger.warning("Target does not support exec/file_transfer; skipping core dump extraction.")
        return
    output_dir = request.config.getoption("core_dumps_output_dir")
    logger.info(f"Core dump extraction enabled, writing to {output_dir}")
    try:
        _extract_core_dumps(target, output_dir)
    except Exception:
        logger.warning("Core dump extraction failed", exc_info=True)
