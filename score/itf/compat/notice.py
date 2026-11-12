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
"""The notice a run on the compatibility layer gives: a warning class of its own, so a project can filter it."""


class ItfCompatibilityWarning(DeprecationWarning):
    """Issued once per run on the compatibility layer, naming the original entry points the run used."""
