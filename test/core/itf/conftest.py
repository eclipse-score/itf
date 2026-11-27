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
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
if str(FIXTURES_DIR) not in sys.path:
    sys.path.insert(0, str(FIXTURES_DIR))


@pytest.fixture(autouse=True)
def _artifacts_beside_each_nested_run(monkeypatch):
    """Nested pytest runs write itf-run/ in their own root, not in this Bazel test's outputs."""
    monkeypatch.delenv("TEST_UNDECLARED_OUTPUTS_DIR", raising=False)
    for name in ("ITF_TARGET", "ITF_OVERRIDE"):
        monkeypatch.delenv(name, raising=False)
