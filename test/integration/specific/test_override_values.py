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
"""An override file: the facts of one physical setup, merged by role into the target file.

Only the target given `overrides = [...]` runs this (it is the one with ITF_OVERRIDE set). The override file
(overrides/localhost.itf.yaml) says where the local platform keeps its working directory; the target file does not."""

import os

import pytest

import score.itf as itf


@itf.requires("platform")
def test_the_platform_uses_the_directory_the_override_values_name(target):
    if not os.environ.get("ITF_OVERRIDE"):
        pytest.skip("this target has no override file")
    assert str(target.platform.root).endswith("itf-local-bench")
