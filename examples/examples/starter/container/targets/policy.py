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
"""Readiness for the container starter."""

from score.itf.core import hookimpl


@hookimpl
def itf_verify(session):
    """Checked once after bring-up: the container runs and answers a command."""
    target = session.target
    code, output = target.command.exec("echo -n ready")
    session.check("command.answers", code == 0 and output.strip() == b"ready", detail=f"exit {code}, output {output!r}")
    session.check("platform.running", target.platform.running())
