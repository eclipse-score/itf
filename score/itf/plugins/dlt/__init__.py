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
"""The original dlt plugin, served by the compatibility layer; the DLT classes are the dlt pack's."""

from score.itf.compat.plugins.dlt import dlt, dlt_config, dlt_on_target, pytest_addoption  # noqa: F401
from score.itf.packs.dlt.on_target.receiver import DltReceiver  # noqa: F401
from score.itf.packs.dlt.receive.process import DltReceive, Protocol, protocol_arguments  # noqa: F401
from score.itf.compat.utils import Bunch  # noqa: F401
