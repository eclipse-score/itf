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
"""pytest's part of the integration suite: one INFO line per scenario and per verdict, so the log reads as a story.
ITF's part (readiness checks, evidence, the dlt-daemon) is the policy above the target files (targets/policy.py).
"""

import logging

import pytest

log = logging.getLogger("integration")


@pytest.fixture(autouse=True)
def _narrate(request):
    """One INFO line per scenario, so the log reads as a story (details stay at DEBUG)."""
    log.info("scenario: %s", request.node.name.removeprefix("test_").replace("_", " "))
    yield


def pytest_runtest_logreport(report):
    if report.when == "call" or report.outcome == "skipped":
        log.info("verdict: %s %s", report.nodeid.split("::")[-1], report.outcome)


@pytest.fixture
def project_value():
    """A project's own fixture, served beside `target` (main's tests called it fixture42)."""
    yield 42
