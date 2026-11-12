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
"""In-memory log stream provider, for offline runs."""

from collections.abc import Iterator
from score.itf.core import capability

from .logs import EndpointLike, LogStream, PlatformLike


@capability("observe.logs", label="logs")
def make_logs(endpoint: EndpointLike, platform: PlatformLike) -> Iterator[LogStream]:
    logs = LogStream(endpoint, platform)
    yield logs
    logs.close()
