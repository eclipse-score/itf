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
"""An illustrative pack for a hardware bench: a power supply, an SD-card flasher and the board as `platform`.

A sketch of the parts and how they compose, not a bench integration. Every class has the members tests and
actions rely on, and no hardware code: each member raises NotImplementedError naming what it stands for. The glue
that calls those members (the board's start and resets, the flash and start actions) shows one way to compose
them; a real bench will need its own."""
