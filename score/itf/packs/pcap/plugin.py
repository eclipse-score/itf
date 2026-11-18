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
"""Entrypoint: tcpdump capture, started once the platform is up (`pcap.start`) or on a host interface
that already exists, with no prerequisite (`pcap.start_on_host`); name one with `by:`."""

pytest_plugins = ["score.itf.packs.pcap.providers", "score.itf.packs.pcap.steps", "score.itf.packs.pcap.host_steps"]
