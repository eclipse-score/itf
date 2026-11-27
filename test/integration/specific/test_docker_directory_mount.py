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
"""A Docker target can bind-mount a host directory declared in its target file."""

import score.itf as itf


@itf.requires("command")
def test_directory_mount_exposes_all_files(target):
    assert target.command.exec("test -f /extra/mount/UTC")[0] == 0
