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
"""`itf contracts map`, `new` and `check`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import cli_parts  # noqa: E402

from score.itf.cli import main as cli  # noqa: E402
from score.itf.cli.main import main  # noqa: E402

DEFINITIONS = str(Path(__file__).parent / "definitions")
PROJECT = ["project.itf.yaml", "--packs", "sim", "--definitions", DEFINITIONS]


@pytest.fixture(autouse=True)
def project(tmp_path):
    """An explicit target declares the project's parts for contract inventory."""
    (tmp_path / "policy.py").write_text(Path(cli_parts.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "project.itf.yaml").write_text(
        "policies: [policy.py]\ncapabilities:\n  platform:\n    factory: sim.platform\n    with:\n      name: inventory\n",
        encoding="utf-8",
    )


def run(capsys, *argv):
    code = main(["contracts", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ---- map ----------------------------------------------------------------------------------------------------


def test_the_map_lists_offerers_with_shapes_needers_with_expectations_and_definitions(capsys):
    code, out, _ = run(capsys, "map", *PROJECT)
    assert code == 0
    assert "acme/toggle  [capability]  defined v1 (stable)" in out
    assert "offered by local.good_switch: is_on" in out
    assert "needed by  local.panel (switch): expects flip" in out


def test_the_map_reports_disagreements(capsys):
    _, out, _ = run(capsys, "map", *PROJECT)
    assert "DISAGREES  missing-member: local.panel (slot switch) expects acme/toggle.flip" in out
    assert "DISAGREES  missing-definition-member: local.dial offers acme/dial without turn" in out


def test_the_map_reads_the_requirements_of_tests_without_importing_them(tmp_path, capsys):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text(
        "import itf\n\n@itf.requires('toggler', contract='acme/toggle', shape=['is_on', 'wiggle'])\n"
        "def test_a():\n    raise SystemExit('imported')\n",
        encoding="utf-8",
    )
    _, out, _ = run(capsys, "map", *PROJECT, "--tests", str(tests))
    assert "test_a.py::test_a (role toggler): is_on, wiggle" in out
    assert "test " in out and "requires acme/toggle.wiggle, which no offerer has" in out


def test_the_map_as_json_mermaid_and_html(tmp_path, capsys):
    _, out, _ = run(capsys, "map", *PROJECT, "--format", "json")
    data = json.loads(out)
    toggle = next(c for c in data["contracts"] if c["contract"] == "acme/toggle")
    assert toggle["definition"]["version"] == 1 and toggle["checks"] == ["a_switch_starts_off"]
    assert {"packs", "contracts", "factories", "actions", "errors"} <= set(data)
    _, out, _ = run(capsys, "map", *PROJECT, "--format", "mermaid")
    assert out.startswith("flowchart LR") and "local.good_switch" in out
    page = tmp_path / "map.html"
    code, out, _ = run(capsys, "map", *PROJECT, "--format", "html", "--output", str(page))
    text = page.read_text(encoding="utf-8")
    assert code == 0 and text.startswith("<!doctype html>")
    assert "acme/toggle" in text and "local.good_switch" in text and "sim.start" in text


def test_the_map_is_deterministic(capsys):
    assert run(capsys, "map", *PROJECT, "--format", "html")[1] == run(capsys, "map", *PROJECT, "--format", "html")[1]


# ---- new ----------------------------------------------------------------------------------------------------


def test_new_writes_a_block_style_skeleton_from_observed_shapes_and_never_overwrites(tmp_path, capsys):
    out_file = tmp_path / "panel.yaml"
    code, out, _ = run(
        capsys, "new", "acme/panel", "project.itf.yaml", "--from-usage", "--packs", "sim", "--out", str(out_file)
    )
    assert code == 0
    text = out_file.read_text(encoding="utf-8")
    assert "contract: acme/panel" in text and "TODO" in text
    assert "{" not in text and "[" not in text  # block style only
    code, _, err = run(
        capsys, "new", "acme/panel", "project.itf.yaml", "--from-usage", "--packs", "sim", "--out", str(out_file)
    )
    assert code == 1 and "not overwriting" in err


def test_new_builds_the_members_from_what_is_expected_and_published(tmp_path, capsys):
    out_file = tmp_path / "flip.yaml"
    # no definition is loaded, so the shapes seen are the members
    code, _, _ = run(
        capsys, "new", "acme/toggle", "project.itf.yaml", "--from-usage", "--packs", "sim", "--out", str(out_file)
    )
    assert code == 0
    import yaml

    skeleton = yaml.safe_load(out_file.read_text(encoding="utf-8"))["contracts"][0]
    assert [m["name"] for m in skeleton["members"]] == ["flip", "is_on"]
    assert skeleton["members"][0].get("required", True) and skeleton["members"][1]["required"] is False


def test_new_refuses_a_name_that_is_defined_or_unused(tmp_path, capsys):
    code, _, err = run(capsys, "new", "acme/toggle", *PROJECT, "--from-usage", "--out", str(tmp_path / "t.yaml"))
    assert code == 1 and "already defined" in err
    code, _, err = run(capsys, "new", "acme/unknown", *PROJECT, "--from-usage", "--out", str(tmp_path / "u.yaml"))
    assert code == 1 and "not in use" in err
    assert run(capsys, "new", "acme/panel")[0] == 2  # --from-usage is required


# ---- check --------------------------------------------------------------------------------------------------


def rules_file(tmp_path, text):
    path = tmp_path / "rules.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_check_exits_1_on_violations_and_names_them(tmp_path, capsys):
    rules = rules_file(tmp_path, "namespaces:\n  - acme\nforbid_stability:\n  - experimental\n")
    code, out, err = run(capsys, "check", "project.itf.yaml", "--rules", rules, "--packs", "sim")
    assert code == 1
    assert "violation (namespaces): acme/panel is in use but has no definition" in err
    assert "violation(s)" in out


def test_check_passes_when_the_rules_hold(tmp_path, capsys):
    rules = rules_file(tmp_path, "forbid_stability:\n  - deprecated\n")
    code, out, _ = run(capsys, "check", "project.itf.yaml", "--rules", rules, "--packs", "sim")
    assert code == 0 and "0 violation(s)" in out


def test_check_covers_the_roles_of_the_given_target_files(tmp_path, capsys):
    target = tmp_path / "t.itf.yaml"
    target.write_text("policies: [policy.py]\ncapabilities:\n  switch: local.good_switch\n", encoding="utf-8")
    rules = rules_file(tmp_path, "roles:\n  switch: acme/other\n")
    code, _, err = run(capsys, "check", "--rules", rules, str(target))
    assert code == 1 and "role switch is acme/toggle, the rules say it is always acme/other" in err


def test_check_reports_rules_with_an_unknown_rule(tmp_path, capsys):
    code, _, err = run(capsys, "check", "--rules", rules_file(tmp_path, "colours:\n  - red\n"), "--packs", "sim")
    assert code == 2 and "unknown rule" in err


def test_conformance_runs_the_checks_against_the_roles_of_a_target_file(tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).parent / "fixtures"))
    target = tmp_path / "t.itf.yaml"
    target.write_text(
        "policies: [policy.py]\ncapabilities:\n  good: local.good_switch\n  bad: local.bad_switch\n", encoding="utf-8"
    )
    rules = rules_file(tmp_path, "forbid_stability:\n  - deprecated\n")
    code, out, err = run(capsys, "check", "--rules", rules, str(target), "--conformance", "--definitions", DEFINITIONS)
    assert code == 1
    assert "[pass]" in out and "good (local.good_switch) acme/toggle: a_switch_starts_off" in out
    assert "[fail]" in out and "bad (local.bad_switch)" in out
    assert "violation (conformance): bad (local.bad_switch) fails a_switch_starts_off" in err


def test_conformance_says_which_factories_it_could_not_run(tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).parent / "fixtures"))
    target = tmp_path / "t.itf.yaml"
    target.write_text("policies: [policy.py]\ncapabilities:\n  good: local.good_switch\n", encoding="utf-8")
    rules = rules_file(tmp_path, "conformance: true\n")
    code, out, _ = run(capsys, "check", "--rules", rules, str(target), "--definitions", DEFINITIONS)
    assert code == 0
    assert "[ not run ] local.bad_switch (acme/toggle): no target file given contains it" in out


# ---- a target file as the scope -------------------------------------------------------------------------------

VENDOR_PLUGIN = """
from score.itf import capability


class Thing:
    def go(self) -> None: ...


@capability("acme/thing@1")
def make() -> Thing:
    return Thing()
"""

VENDOR_DEFINITION = """
contracts:
  - contract: acme/thing
    kind: capability
    version: 1
    summary: A thing that goes.
    members:
      - name: go
        signature: "() -> None"
        semantics: Goes.
"""


def _vendor_project(tmp_path, monkeypatch):
    """A pack that is not installed (located by the target file), its definition in its own contracts/
    directory, a target file, a test and an empty policy beside them."""
    pack = tmp_path / "vendor" / "vendorpack"
    (pack / "contracts").mkdir(parents=True)
    (pack / "__init__.py").write_text("", encoding="utf-8")
    (pack / "pack.yaml").write_text("name: vendorpack\nversion: 0.1.0\n", encoding="utf-8")
    (pack / "plugin.py").write_text(VENDOR_PLUGIN, encoding="utf-8")
    (pack / "contracts" / "thing.yaml").write_text(VENDOR_DEFINITION, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path / "vendor"))
    project = tmp_path / "project"
    project.mkdir()
    (project / "policy.py").write_text("", encoding="utf-8")
    (project / "test_thing.py").write_text(
        'import score.itf as itf\n\n\n@itf.requires("thing", contract="acme/thing")\ndef test_go(target):\n'
        "    target.thing.go()\n",
        encoding="utf-8",
    )
    target = project / "target.itf.yaml"
    target.write_text(
        "packs:\n  vendorpack: vendorpack.plugin\ncapabilities:\n  thing: vendorpack.make\n", encoding="utf-8"
    )
    return str(target)


def test_a_map_of_a_target_file_shows_only_what_it_uses_and_finds_a_located_pack(capsys, tmp_path, monkeypatch):
    target = _vendor_project(tmp_path, monkeypatch)
    code, out, err = run(capsys, "map", target, "--format", "json")
    assert code == 0, err
    data = json.loads(out)
    assert [(c["contract"], c["defined"]) for c in data["contracts"]] == [("acme/thing", True)]
    assert "test_go" in out


def test_check_and_map_load_the_declared_policy_once(capsys, tmp_path, monkeypatch):
    target = _vendor_project(tmp_path, monkeypatch)
    policy = Path(target).parent / "policy.py"
    imports = tmp_path / "policy-imports"
    policy.write_text(
        f"from pathlib import Path\nwith Path({str(imports)!r}).open('a') as output:\n    output.write('loaded\\n')\n"
        "from score.itf import capability\n\n\nclass Lamp:\n    def light(self) -> None: ...\n\n\n"
        '@capability("bench/lamp")\ndef lamp() -> Lamp:\n    return Lamp()\n',
        encoding="utf-8",
    )
    Path(target).write_text(
        Path(target).read_text(encoding="utf-8") + f"  lamp: local.lamp\npolicies: [{json.dumps(str(policy))}]\n",
        encoding="utf-8",
    )
    rules = tmp_path / "rules.yaml"
    rules.write_text("namespaces:\n  - acme\n", encoding="utf-8")
    code, out, err = run(capsys, "check", "--rules", str(rules), target)
    assert code == 0, err
    assert "0 violation(s)" in out
    code, out, err = run(capsys, "map", target, "--format", "json")
    assert code == 0, err
    lamps = [contract for contract in json.loads(out)["contracts"] if contract["contract"] == "bench/lamp"]
    assert len(lamps) == 1 and "local.lamp" in out
    assert imports.read_text(encoding="utf-8").splitlines() == ["loaded"]
