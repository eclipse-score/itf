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
"""The sim pack: a whole target in memory, composed like a real one, no `by:` needed (it is a pack of its own).
Its shell does not wait for the platform by itself: the target file says so with `relations:`."""

import pytest

from score.itf.core import compose, Session

TARGET_FILE = """
capabilities:
  platform:
    factory: sim.platform
    with:
      name: dut
  command: sim.exec
  endpoint:
    factory: net.endpoint
    with:
      host: 127.0.0.1
      port: 22
  credentials:
    factory: net.password
    with:
      user: score
  shell: sim.shell
goals:
  - platform.up
  - shell.open
  - network.reachable
relations:
  - state: shell.open
    after:
      - platform.up
"""


def test_a_sim_target_comes_up_and_unwinds(tmp_path):
    with compose(target=TARGET_FILE, run_dir=tmp_path / "run") as session:
        assert session.target.names() == ("command", "credentials", "endpoint", "platform", "shell")
        assert session.target.platform.running
        assert session.target.shell.is_connected()
        assert {"platform.up", "shell.open", "network.reachable"} <= {
            s.rpartition(":")[2] for s in session._last_observed
        }


def test_the_plan_names_the_sim_actions(tmp_path):
    session = Session(target=TARGET_FILE, plan_only=True, run_dir=tmp_path / "run").resolve()
    by = {d.rpartition(":")[2]: s.impl.rpartition(":")[2] for s in session._action_plan.steps for d in s.delivers}
    assert by["platform.up"] == "start_platform" and by["shell.open"] == "open_session"


def test_the_relation_in_the_target_file_orders_the_shell_after_the_platform(tmp_path):
    session = Session(target=TARGET_FILE, plan_only=True, run_dir=tmp_path / "run").resolve()
    order = [d.rpartition(":")[2] for s in session._action_plan.steps for d in s.delivers]
    assert order.index("platform.up") < order.index("shell.open")


def test_the_real_packs_stay_out_of_a_sim_target_file(tmp_path):
    session = Session(target=TARGET_FILE, plan_only=True, run_dir=tmp_path / "run").resolve()
    assert session._catalog.packs() == ("net", "sim")


def test_a_second_device_shares_the_platform_and_has_its_own_capture(tmp_path):
    text = (
        TARGET_FILE
        + """scopes:
  gw:
    capabilities:
      capture: sim.capture
    share:
      - platform
    goals:
      - capture.running
"""
    )
    with compose(target=text, run_dir=tmp_path / "run") as session:
        assert session.target.gw.names() == ("capture", "platform")
        assert session.target.gw.platform is session.target.platform
        assert session.target.gw.capture.running


def test_a_sim_target_file_without_its_platform_says_which_factory_to_list(tmp_path):
    from score.itf.core import ResolutionFailed

    with pytest.raises(ResolutionFailed, match="Candidates: sim.platform"):
        Session(target="capabilities:\n  command: sim.exec\n", plan_only=True, run_dir=tmp_path / "run").resolve()
