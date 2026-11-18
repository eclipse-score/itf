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
"""The original core dump plugin: `--extract-core-dumps` copies core files from the target after each test (each
session, with --keep-target), through the target file's `command` and `files` roles and the core_dump pack."""

import logging
import os
from types import SimpleNamespace

import pytest

from score.itf.packs.core_dump.extract import extract_core_dumps

from .core import determine_target_scope

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
        default=os.path.join(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "/tmp"), "coredumps"),
        help="Directory to write extracted core dump files. "
        "Defaults to $TEST_UNDECLARED_OUTPUTS_DIR/coredumps or /tmp/coredumps.",
    )


@pytest.fixture(scope=determine_target_scope, autouse=True)
def _core_dump_extraction(request, target):
    """Extracts core dumps after the test, when --extract-core-dumps is set and the target can (exec and
    file_transfer)."""
    yield
    if not request.config.getoption("extract_core_dumps"):
        return
    if not target.has_all_capabilities({"exec", "file_transfer"}):
        logger.warning("Target does not support exec/file_transfer; skipping core dump extraction.")
        return
    output_dir = request.config.getoption("core_dumps_output_dir")
    logger.info(f"Core dump extraction enabled, writing to {output_dir}")
    try:
        # any original Target: its execute and download are what the pack's command and files roles offer
        command = SimpleNamespace(exec=lambda cmd, timeout=30.0: target.execute(cmd))
        extract_core_dumps(command, target, output_dir)
    except Exception:
        logger.warning("Core dump extraction failed", exc_info=True)
