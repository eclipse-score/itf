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
"""In-memory shell provider, for offline runs."""

from collections.abc import Iterator
from score.itf.core import capability

from .session import Credentials, Endpoint, Platform, SimSession


@capability("exec.shell", label="shell")
def make_session(endpoint: Endpoint, credentials: Credentials, platform: Platform) -> Iterator[SimSession]:
    session = SimSession(endpoint, credentials, platform)
    yield session
    session.close()
