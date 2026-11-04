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
"""Readiness and evidence for the SSH starter."""

import logging
import os
from pathlib import Path

from score.itf.core import hookimpl


log = logging.getLogger("starter.ssh")
EVIDENCE = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", ".")) / "evidence"


@hookimpl
def itf_verify(session):
    """Checked once after bring-up: the SSH session is open and a command answers."""
    target = session.target
    session.check("shell.connected", target.shell.is_connected())
    code, output = target.command.exec("echo -n ready")
    session.check("command.answers", code == 0 and output.strip() == b"ready", detail=f"exit {code}, output {output!r}")


@hookimpl
def itf_teardown(session):
    """Saves what the machine says about itself before teardown."""
    target = session.target
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if target.shell.is_connected():
        code, lines, _ = target.shell.execute_command_output("uname -a; id")
        output = "".join(lines)
        (EVIDENCE / "machine.txt").write_text(output, encoding="utf-8")
        log.info("teardown: machine identity (exit %s) saved to %s", code, EVIDENCE / "machine.txt")
