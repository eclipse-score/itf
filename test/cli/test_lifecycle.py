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
"""`itf validate`, `graph`, `up --detach`, `down` and `test`."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import cli_parts  # noqa: E402

from score.itf.cli import main as cli  # noqa: E402
from score.itf.cli.main import main  # noqa: E402

DEFINITIONS = str(Path(__file__).parent / "definitions")

SIM = """
capabilities:
  platform:
    factory: sim.platform
    with:
      name: box
      state_dir: {state}
  command: sim.exec
goals:
  - platform.up
"""


def write(tmp_path, text, name="target.itf.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.fixture
def project(tmp_path):
    """The project's own parts, explicitly declared by targets that use them."""
    (tmp_path / "policy.py").write_text(Path(cli_parts.__file__).read_text(encoding="utf-8"), encoding="utf-8")


# ---- validate -----------------------------------------------------------------------------------------------


def test_validate_says_ok_and_constructs_nothing(tmp_path, capsys):
    target = write(tmp_path, SIM.format(state=tmp_path / "state"))
    assert main(["validate", target]) == 0
    assert "ok:" in capsys.readouterr().out
    assert not (tmp_path / "state").exists()


def test_validate_uses_the_configured_target_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ITF_TARGET", write(tmp_path, SIM.format(state=tmp_path)))
    assert main(["validate"]) == 0


def test_validate_exits_1_with_the_gate_diagnostics(tmp_path, capsys):
    assert main(["validate", write(tmp_path, "capabilities:\n  command: sim.exec\n")]) == 1
    err = capsys.readouterr().err
    assert "plan failed at gate 1" in err and "Candidates: sim.platform" in err


def test_validate_reports_a_wrong_setting_with_the_role(tmp_path, capsys):
    text = "capabilities:\n  platform:\n    factory: sim.platform\n    with:\n      nam: x\n"
    assert main(["validate", write(tmp_path, text)]) == 1
    assert "platform (sim.platform)" in capsys.readouterr().err


def test_validate_reports_an_unknown_factory_and_a_relation_naming_nothing(tmp_path, capsys):
    assert main(["validate", write(tmp_path, "capabilities:\n  command: sim.nope\n")]) == 1
    assert "not a known capability factory" in capsys.readouterr().err
    text = SIM.format(state=tmp_path) + "relations:\n  - state: ghost.state\n    after:\n      - platform.up\n"
    assert main(["validate", write(tmp_path, text, "r.itf.yaml")]) == 1
    assert "no listed action makes 'ghost.state'" in capsys.readouterr().err


def test_validate_checks_the_parts_against_their_definitions(tmp_path, monkeypatch, project, capsys):
    monkeypatch.setenv("ITF_CONTRACTS_PATH", DEFINITIONS)
    target = write(tmp_path, "policies: [policy.py]\ncapabilities:\n  dial: local.dial\n")
    assert main(["validate", target]) == 1
    assert "local.dial offers acme/dial without turn, which its definition requires" in capsys.readouterr().err
    monkeypatch.delenv("ITF_CONTRACTS_PATH")
    assert main(["validate", target]) == 0


# ---- plan ---------------------------------------------------------------------------------------------------


def test_plan_names_the_action_of_each_step(tmp_path, capsys):
    assert main(["plan", write(tmp_path, SIM.format(state=tmp_path))]) == 0
    assert "platform.up by sim.start" in capsys.readouterr().out


# ---- graph --------------------------------------------------------------------------------------------------


def test_graph_topology_has_roles_factories_contracts_and_slots(tmp_path, capsys):
    target = write(tmp_path, SIM.format(state=tmp_path))
    assert main(["graph", target, "--kind", "topology"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("flowchart LR")
    assert 'n_command["command<br/>sim.exec<br/>exec.command"]' in out
    assert 'n_platform["platform<br/>sim.platform<br/>platform.instance"]' in out
    assert "n_command -->|platform| n_platform" in out


def test_graph_topology_draws_scopes_and_shares(tmp_path, capsys):
    text = SIM.format(state=tmp_path) + (
        "scopes:\n  gw:\n    capabilities:\n      command: sim.exec\n    share:\n      - platform\n"
    )
    assert main(["graph", write(tmp_path, text), "--kind", "topology"]) == 0
    out = capsys.readouterr().out
    assert 'subgraph s_gw["scope gw"]' in out
    assert "n_gw_platform -.->|shares| n_platform" in out
    assert "n_gw_command -->|platform| n_platform" in out


def test_graph_sequence_marks_probes_goals_after_and_breaks(tmp_path, project, capsys):
    text = (
        "policies: [policy.py]\ncapabilities: {}\ngoals:\n  - acme/x\n  - acme/y\n  - acme/z\n"
        "relations:\n  - state: acme/y\n    after:\n      - acme/x\n"
    )
    assert main(["graph", write(tmp_path, text), "--kind", "sequence"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("flowchart TB")
    assert "local.make_y<br/>probe: skipped when it holds" in out  # a probe: the step can be skipped
    assert "local.make_x<br/>no probe: always runs" in out
    assert "|after acme/x|" in out and "|breaks acme/x|" in out
    assert "classDef goal" in out


def test_graph_both_is_two_fenced_blocks_and_the_default(tmp_path, capsys):
    target = write(tmp_path, SIM.format(state=tmp_path))
    assert main(["graph", target]) == 0
    out = capsys.readouterr().out
    assert out.count("```mermaid") == 2 and "%% topology" in out and "%% sequence" in out
    assert main(["graph", target, "--kind", "sequence"]) == 0
    assert "```" not in capsys.readouterr().out


def test_graph_of_a_target_file_that_does_not_compile_exits_1(tmp_path, capsys):
    assert main(["graph", write(tmp_path, "capabilities:\n  command: sim.exec\n")]) == 1


def test_validate_ignores_undeclared_policies_beside_the_target_and_in_the_cwd(tmp_path, capsys):
    targets = tmp_path / "targets"
    targets.mkdir()
    for directory in (tmp_path, targets):
        (directory / "policy.py").write_text("raise AssertionError('undeclared policy imported')\n", encoding="utf-8")
    assert main(["validate", write(targets, SIM.format(state=tmp_path / "state"))]) == 0
    assert "ok:" in capsys.readouterr().out


@pytest.mark.parametrize("absolute", [False, True], ids=["invocation-cwd", "absolute"])
def test_validate_loads_an_explicit_policy_outside_the_target_directory(tmp_path, project, capsys, absolute):
    targets = tmp_path / "targets"
    targets.mkdir()
    (targets / "policy.py").write_text("raise AssertionError('wrong policy imported')\n", encoding="utf-8")
    policy = str(tmp_path / "policy.py") if absolute else "policy.py"
    target = write(targets, f"policies: [{json.dumps(policy)}]\ncapabilities:\n  dial: local.dial\n")
    assert main(["validate", target]) == 0
    assert "ok:" in capsys.readouterr().out


def test_validate_reports_a_missing_declared_policy(tmp_path, capsys):
    target = write(tmp_path, "policies: [missing.py]\ncapabilities: {}\n")
    assert main(["validate", target]) != 0
    error = capsys.readouterr().err
    assert "policy" in error and "missing.py" in error and "is not a file" in error


# ---- up --detach and down -----------------------------------------------------------------------------------


def test_detach_leaves_it_up_and_down_takes_it_down_in_a_fresh_session(tmp_path, capsys):
    state = tmp_path / "state"
    target = write(tmp_path, SIM.format(state=state))
    run = ["--run-dir", str(tmp_path / "run")]
    assert main(["up", "--detach", target, *run]) == 0
    assert "detached" in capsys.readouterr().out
    assert (state / "box.up").is_file()  # nothing unwound it
    assert main(["down", target, *run]) == 0
    out = capsys.readouterr().out
    assert "observed (1): platform.up" in out and "dismantled (1): platform" in out
    assert not (state / "box.up").exists()
    assert main(["down", target, *run]) == 0
    assert "nothing held" in capsys.readouterr().out


def test_up_without_detach_unwinds_what_it_built(tmp_path, capsys):
    state = tmp_path / "state"
    assert main(["up", write(tmp_path, SIM.format(state=state)), "--run-dir", str(tmp_path / "run")]) == 0
    assert not (state / "box.up").exists()


def test_detach_and_down_are_refused_for_a_factory_that_cannot_observe(tmp_path, capsys):
    target = write(tmp_path, SIM.format(state="").replace("      state_dir: \n", ""))
    run = ["--run-dir", str(tmp_path / "run")]
    assert main(["up", "--detach", target, *run]) == 1
    err = capsys.readouterr().err
    assert "--detach refused" in err and "platform (sim.platform)" in err and "observes=True" in err
    assert main(["down", target, *run]) == 1
    assert "down refused" in capsys.readouterr().err


def test_local_observes_only_with_a_root(tmp_path, capsys):
    plain = write(tmp_path, "capabilities:\n  platform: localhost.platform\ngoals:\n  - platform.up\n")
    assert main(["down", plain, "--run-dir", str(tmp_path / "run")]) == 1
    rooted = write(
        tmp_path,
        f"capabilities:\n  platform:\n    factory: localhost.platform\n    with:\n      root: {tmp_path / 'bench'}\n"
        "goals:\n  - platform.up\n",
        "rooted.itf.yaml",
    )
    run = ["--run-dir", str(tmp_path / "run")]
    assert main(["up", "--detach", rooted, *run]) == 0
    assert (tmp_path / "bench").is_dir()
    assert main(["down", rooted, *run]) == 0
    assert not (tmp_path / "bench").exists()


# ---- test ---------------------------------------------------------------------------------------------------


def test_test_gives_pytest_the_target_file_as_options_and_the_rest_after_dashes(tmp_path, monkeypatch):
    import pytest as pytest_module

    seen = {}
    monkeypatch.setattr(pytest_module, "main", lambda args: seen.update(args=args) or 0)
    monkeypatch.setattr(cli, "_adapter_is_installed", lambda: False)
    before = dict(os.environ)
    target_file = write(tmp_path, SIM.format(state=tmp_path))
    over = write(tmp_path, "capabilities: {}\n", "lab.itf.yaml")
    assert main(["test", target_file, "--override", over, "--", "-k", "fast", "tests/"]) == 0
    assert seen["args"] == [
        "-p",
        cli.ADAPTER,
        f"--itf-target={target_file}",
        f"--itf-override={over}",
        "-k",
        "fast",
        "tests/",
    ]
    assert dict(os.environ) == before  # nothing is exported for pytest to read


def test_test_finds_the_target_file_as_the_other_commands_do(tmp_path, monkeypatch):
    import pytest as pytest_module

    seen = {}
    monkeypatch.setattr(pytest_module, "main", lambda args: seen.update(args=args) or 0)
    monkeypatch.setattr(cli, "_adapter_is_installed", lambda: True)
    target_file = write(tmp_path, SIM.format(state=tmp_path))
    (tmp_path / "pytest.ini").write_text("[pytest]\nitf_target = target.itf.yaml\n", encoding="utf-8")
    assert main(["test", "--", "-x"]) == 0
    assert seen["args"] == [f"--itf-target={target_file}", "-x"]
    assert main(["test"]) == 0 and seen["args"] == [f"--itf-target={target_file}"]


def test_test_runs_the_tests_against_the_target_file(tmp_path):
    test = tmp_path / "test_it.py"
    test.write_text(
        "import pytest\nfrom score.itf.core import requires\n\n"
        "@requires('command')\ndef test_runs(target):\n    assert target.command.exec('x') == (0, b'ok:x')\n",
        encoding="utf-8",
    )
    target_file = write(tmp_path, SIM.format(state=tmp_path / "state"))
    assert main(["test", target_file, "--", "-p", "no:cacheprovider", "-q", str(test)]) == 0
