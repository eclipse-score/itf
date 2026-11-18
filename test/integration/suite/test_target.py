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
"""Any target: what a test gets beside the roles it asks for."""

import pytest

import score.itf as itf


def test_a_project_fixture_is_served_beside_the_target(project_value, target):
    assert project_value == 42 and target is not None


def test_the_target_has_only_the_roles_its_target_file_lists(target):
    assert target.names() and not target.has("no_such_role")


@itf.requires("no_such_role")
def test_a_test_needing_a_role_the_target_lacks_is_deselected(target):
    pytest.fail("gating should have deselected this test: no target file has a no_such_role role")
