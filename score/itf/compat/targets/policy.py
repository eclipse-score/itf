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
"""The legacy project's policy, beside the target files the original options select: readiness and evidence."""

import logging
import os
from pathlib import Path

from score.itf.core import hookimpl

logger = logging.getLogger("legacy")

EVIDENCE = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", ".")) / "evidence"


@hookimpl
def itf_verify(session):
    """Nothing to check yet for a docker target file: the container is started per test by the `target` fixture
    (as the original plugin did), so only what the session itself has up is verified."""
    target = session.target
    logger.info("verify: target offers %s", ", ".join(sorted(target.names())))
    if target.has("platform") and target.platform.running() and target.has("command"):
        code, output = target.command.exec("echo -n ready")
        session.check("command.answers", code == 0 and output.strip().endswith(b"ready"), detail=f"exit {code}")


@hookimpl
def itf_teardown(session):
    """Evidence, collected while the target still runs: the console transcript."""
    target = session.target
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if target.has("console"):
        path = EVIDENCE / "console.txt"
        path.write_text("\n".join(target.console.lines()), encoding="utf-8")
        logger.info("teardown: console transcript (%d lines) saved to %s", len(target.console.lines()), path)
