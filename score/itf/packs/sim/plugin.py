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
"""Entrypoint: in-memory platform, shell, logs and capture, and their actions, for offline runs."""

pytest_plugins = [
    "score.itf.packs.sim.docker.providers",
    "score.itf.packs.sim.docker.steps",
    "score.itf.packs.sim.ssh.providers",
    "score.itf.packs.sim.ssh.steps",
    "score.itf.packs.sim.dlt.providers",
    "score.itf.packs.sim.dlt.steps",
    "score.itf.packs.sim.pcap.providers",
    "score.itf.packs.sim.pcap.steps",
]
