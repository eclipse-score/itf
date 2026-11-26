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
import pytest


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch, tmp_path):
    for name in ("ITF_TARGET", "ITF_OVERRIDE", "BUILD_WORKING_DIRECTORY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
