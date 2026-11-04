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
"""The optional definitions a session may be handed.

The core never imports `score.itf.contracts`; whoever starts a session (the pytest adapter, `score.itf.Session`,
the command line) turns the library's definitions into `gating.Definition` here and injects them. Without the
library (or without any definition) the result is empty, and nothing in the engine depends on it.
"""

from __future__ import annotations

import logging

from .. import gating

logger = logging.getLogger(__name__)


def definitions() -> dict:
    """contract name -> `gating.Definition` for every loaded definition, or nothing when there is no library.
    Raises `ValueError` (`contracts.ContractError`) when a definition file is malformed."""
    try:
        from score.itf import contracts
    except ImportError:
        logger.debug("itf: no contract library available")
        return {}
    return {
        name: gating.Definition(name, d.version, d.stability, d.replaced_by) for name, d in contracts.load().items()
    }
