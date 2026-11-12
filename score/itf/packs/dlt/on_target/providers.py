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
"""The on-target dlt-receive provider. Constructing it touches nothing: the tool is uploaded on the first start."""

from collections.abc import Iterator

from score.itf.core import capability

from .receiver import DltOnTarget, Files, OnTargetConfig, Process


@capability("logs.on_target", label="on_target")
def make_on_target(files: Files, process: Process, config: OnTargetConfig) -> Iterator[DltOnTarget]:
    receivers = DltOnTarget(files, process, config)
    try:
        yield receivers
    finally:
        receivers.close()
