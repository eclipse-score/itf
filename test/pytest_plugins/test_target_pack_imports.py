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
"""Target-selected pack imports and their shared runfiles reach the pytest launcher."""


def test_target_selected_packs_with_shared_dependencies_are_importable():
    import score.itf.core
    import score.itf.packs.localhost.plugin as localhost_plugin
    import score.itf.packs.sim.plugin as sim_plugin

    assert score.itf.core.Session
    assert localhost_plugin.__name__ == "score.itf.packs.localhost.plugin"
    assert sim_plugin.__name__ == "score.itf.packs.sim.plugin"
