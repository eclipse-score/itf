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
"""Readiness and evidence for the serial starter."""

import logging
import os
from pathlib import Path

from score.itf.core import hookimpl


log = logging.getLogger("starter.serial")
EVIDENCE = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", ".")) / "evidence"


@hookimpl
def itf_verify(session):
    """Checked once after bring-up: the console recorded output and a command answers through it."""
    target = session.target
    first = target.console.wait_for("", timeout=10, since=0)
    session.check("console.recorded_boot", first is not None, detail=f"first recorded line: {first!r}")
    code, output = target.command.exec("echo -n ready")
    # endswith, not ==: a console may deliver its boot banner into the first command's output window
    session.check(
        "command.answers", code == 0 and output.strip().endswith(b"ready"), detail=f"exit {code}, output {output!r}"
    )


@hookimpl
def itf_teardown(session):
    """Saves the console transcript before the console is closed."""
    lines = session.target.console.lines()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / "console.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("teardown: console transcript (%d lines) saved to %s", len(lines), path)
