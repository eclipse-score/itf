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
"""The contract library is optional: definitions are data, the map reads declarations, contract rules are checks."""

import sys
from pathlib import Path

import pytest
import yaml

from score.itf import contracts
from score.itf.core.engine import registry
from score.itf.core.engine.publish import publish
from score.itf.core.gating import Requirement

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))
import usage_parts  # noqa: E402


@pytest.fixture(scope="module")
def catalog():
    return publish(registry.register_modules([(usage_parts, "policy")]))


def definition_file(directory, *entries):
    directory.mkdir(exist_ok=True)
    (directory / "defs.yaml").write_text(yaml.safe_dump({"contracts": list(entries)}), encoding="utf-8")
    return directory


def entry(name, kind="capability", **fields):
    return {"contract": name, "kind": kind, "version": 1, "summary": "s", "description": "d", **fields}


# ---- definitions -------------------------------------------------------------------------------------------------


def test_the_supported_definitions_resolve_from_pack_references_to_the_shared_library():
    loaded = contracts.load()
    for name in ("exec.command", "files.transfer", "platform.up", "platform.instance", "descriptor.endpoint"):
        assert name in loaded
    command = loaded["exec.command"]
    assert (command.kind, command.role, command.stability, command.version) == ("capability", "command", "stable", 1)
    assert command.member_names == ("exec",)
    assert command.conformance == "score.itf.contracts.conformance.exec"
    assert command.source == "score.itf.contracts.definitions: exec.command.yaml"


def test_a_definition_needs_no_namespace_registry_and_any_name_works(tmp_path, monkeypatch):
    directory = definition_file(
        tmp_path / "defs",
        entry("acme/power.relay", role="relay", members=[{"name": "switch"}], stability="experimental"),
        entry("whatever", kind="state", stability="deprecated", replaced_by="other"),
    )
    monkeypatch.setenv(contracts.PATH_VARIABLE, str(directory))
    loaded = contracts.load()
    assert loaded["acme/power.relay"].member_names == ("switch",)
    assert loaded["whatever"].replaced_by == "other"
    assert loaded["acme/power.relay"].source.endswith("defs.yaml")


def test_a_missing_directory_in_the_path_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv(contracts.PATH_VARIABLE, str(tmp_path / "nope"))
    with pytest.raises(contracts.ContractError, match="not a directory"):
        contracts.load()


def test_shared_contract_references_resolve_from_the_declaring_file_once(tmp_path, monkeypatch):
    shared = definition_file(tmp_path / "shared", entry("shared.command"))
    first, second = tmp_path / "first", tmp_path / "second"
    for directory in (first, second):
        directory.mkdir()
        (directory / "shared.command.yaml").write_text("$ref: ../shared/defs.yaml\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    found = [
        definition
        for definition in contracts.load_list([first, second, shared])
        if definition.contract == "shared.command"
    ]
    assert len(found) == 1
    assert found[0].source.endswith("defs.yaml")


def test_contract_references_reject_cycles_missing_files_and_overrides(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    first.write_text("$ref: second.yaml\n", encoding="utf-8")
    second.write_text("$ref: first.yaml\n", encoding="utf-8")
    with pytest.raises(contracts.ContractError, match="reference cycle"):
        contracts.read_directory(tmp_path)
    second.unlink()
    with pytest.raises(contracts.ContractError, match="cannot read contract definition"):
        contracts.read_directory(tmp_path)
    first.write_text("$ref: missing.yaml\ncontracts: []\n", encoding="utf-8")
    with pytest.raises(contracts.ContractError, match="must stand alone"):
        contracts.read_directory(tmp_path)


def test_malformed_definitions_name_the_file_and_the_field(tmp_path):
    bad = definition_file(tmp_path / "bad", {"contract": "x.y", "kind": "thing"})
    with pytest.raises(contracts.ContractError, match=r"defs.yaml: x.y: kind must be one of"):
        contracts.read_directory(bad)
    bad = definition_file(tmp_path / "bad2", entry("x.y", "state", members=[{"name": "m"}]))
    with pytest.raises(contracts.ContractError, match="a state has no members"):
        contracts.read_directory(bad)
    bad = definition_file(tmp_path / "bad3", entry("x.y", stability="forever"))
    with pytest.raises(contracts.ContractError, match="stability"):
        contracts.read_directory(bad)
    for version in (0, -1, "one", True):
        bad = definition_file(tmp_path / f"bad-version-{version}", entry("x.y", version=version))
        with pytest.raises(contracts.ContractError, match="positive integer major"):
            contracts.read_directory(bad)


def test_an_entry_point_source_adds_definitions(tmp_path, monkeypatch):
    import importlib.metadata

    directory = definition_file(tmp_path / "vendor", entry("vendor/thing", role="thing"))
    ep = importlib.metadata.EntryPoint(name="vendor", value="vendor_defs:directories", group="score_itf.contracts")
    monkeypatch.setitem(sys.modules, "vendor_defs", type(sys)("vendor_defs"))
    sys.modules["vendor_defs"].directories = lambda: [str(directory)]
    real = importlib.metadata.entry_points
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda **kw: [ep] if kw.get("group") == "score_itf.contracts" else real(**kw),
    )
    assert contracts.load()["vendor/thing"].role == "thing"


def test_two_definitions_of_one_name_are_listed_and_the_first_wins(tmp_path):
    first = definition_file(tmp_path / "a", entry("dup.name", summary="first"))
    second = definition_file(tmp_path / "b", entry("dup.name", summary="second"))
    listed = [d for d in contracts.load_list([first, second]) if d.contract == "dup.name"]
    assert [d.summary for d in listed] == ["first", "second"]
    assert contracts.load([first, second])["dup.name"].summary == "first"


# ---- the map -----------------------------------------------------------------------------------------------------


def test_the_map_lists_offerers_needers_and_tests_per_contract(catalog):
    found = contracts.contract_map(catalog, tests=[("t::a", Requirement("relay", "acme/power.relay", ("switch",)))])
    relay = found["acme/power.relay"]
    assert relay.kind == "capability"
    assert relay.offerers == [("local.relay", ("read", "switch"), 1)]
    needers = {label: (slot, members) for label, slot, members, _ in relay.needers}
    assert needers["local.rack"] == ("relay", ("switch",))
    assert needers["local.cabinet"] == ("relay", ("toggle",))
    assert relay.tests == [("t::a", "relay", ("switch",), None)]
    assert found["acme/power.on"].kind == "state"
    assert found["acme/power.ready"].needers[0][:2] == ("local.power_on", "after")


def test_an_expected_member_no_offerer_has_is_a_disagreement(catalog):
    relay = contracts.contract_map(catalog)["acme/power.relay"]
    missing = [d for d in relay.disagreements if d.kind == "missing-member"]
    assert [d.message for d in missing] == [
        "local.cabinet (slot relay) expects acme/power.relay.toggle, which no offerer has (local.relay)"
    ]


def test_a_test_requiring_a_member_nobody_offers_is_a_disagreement(catalog):
    found = contracts.contract_map(catalog, tests=[("t::b", Requirement("relay", "acme/power.relay", ("flip",)))])
    messages = [d.message for d in found["acme/power.relay"].disagreements if d.kind == "missing-member"]
    assert any("test t::b requires acme/power.relay.flip" in m for m in messages)


def test_a_major_mismatch_is_a_disagreement(catalog):
    relay = contracts.contract_map(catalog)["acme/power.relay"]
    mismatch = [d for d in relay.disagreements if d.kind == "major-mismatch"]
    assert [d.message for d in mismatch] == ["local.lab (slot relay) expects acme/power.relay@2, offered: @1"]


def test_an_offered_major_above_the_definitions_version_is_a_disagreement(catalog):
    definition = contracts.Definition("acme/power.relay", "capability", version=0)
    relay = contracts.contract_map(catalog, definitions={"acme/power.relay": definition})["acme/power.relay"]
    assert any("definition's version is 0" in d.message for d in relay.disagreements)


def test_an_offerer_without_a_required_member_of_the_definition_is_a_disagreement(catalog):
    members = [{"name": "switch"}, {"name": "calibrate"}, {"name": "read", "required": False}]
    found = contracts.contract_map(
        catalog,
        definitions=[
            contracts.Definition(
                "acme/power.relay",
                "capability",
                members=tuple(contracts.Member(m["name"], required=m.get("required", True)) for m in members),
            )
        ],
    )["acme/power.relay"]
    kinds = {d.kind: d.message for d in found.disagreements}
    assert "local.relay offers acme/power.relay without calibrate" in kinds["missing-definition-member"]


def test_two_definitions_are_a_disagreement_and_one_is_attached(catalog):
    one = contracts.Definition("acme/power.relay", "capability", source="a.yaml")
    two = contracts.Definition("acme/power.relay", "capability", source="b.yaml")
    relay = contracts.contract_map(catalog, definitions=[one, two])["acme/power.relay"]
    assert relay.definition is one
    assert [d.message for d in relay.disagreements if d.kind == "two-definitions"] == [
        "acme/power.relay is defined 2 times: a.yaml, b.yaml"
    ]


def test_agreement_has_no_disagreements():
    from score.itf.core.engine import packs

    local = publish(registry.register_modules(registry.expand([packs.load("localhost")])))
    found = contracts.contract_map(local, definitions=contracts.load())
    assert found["exec.command"].offerers and found["exec.command"].definition is not None
    assert [d for item in found.values() for d in item.disagreements] == []


def test_the_map_is_json_ready(catalog):
    import json

    found = contracts.contract_map(catalog)
    text = json.dumps({n: e.to_json() for n, e in found.items()})
    assert "acme/power.relay" in text


def test_policy_baselines_and_strict_runtime_test_requirements_are_in_the_map(catalog):
    from dataclasses import replace
    from typing import Protocol

    from score.itf.core.engine.publish import declared_expectations
    from score.itf.core.gating import requires

    class RelayAPI(Protocol):
        __contract__ = "acme/power.relay@2"

        def switch(self, enabled: bool) -> None: ...

    policy = type(sys)("project.policy")
    policy.itf_expect = RelayAPI
    catalog = replace(catalog, expectations=declared_expectations(policy))
    requirement = requires("relay", shape=RelayAPI).requirement
    mapped = contracts.contract_map(catalog, tests=[("test_relay", requirement)])
    relay = mapped["acme/power.relay"]
    assert ("project.policy", "itf_expect", ("switch",), 2) in relay.needers
    assert relay.tests == [("test_relay", "relay", ("switch",), 2)]
    assert any(
        "project.policy (slot itf_expect) expects acme/power.relay@2" in item.message for item in relay.disagreements
    )


# ---- skeletons ---------------------------------------------------------------------------------------------------


def test_a_skeleton_is_built_from_the_shapes_observed(catalog):
    found = contracts.contract_map(catalog, tests=[("t", Requirement("relay", "acme/power.relay", ("switch",)))])
    skeleton = contracts.skeleton_from_usage("acme/power.relay", found)
    assert skeleton["contract"] == "acme/power.relay" and skeleton["kind"] == "capability"
    assert skeleton["role"] == "relay" and skeleton["version"] == 2
    members = {m["name"]: m for m in skeleton["members"]}
    assert set(members) == {"switch", "toggle", "read"}
    assert "required" not in members["switch"] and members["read"]["required"] is False  # offered, never expected
    assert yaml.safe_load(yaml.safe_dump(skeleton)) == skeleton


def test_a_skeleton_of_a_state_has_no_members(catalog):
    skeleton = contracts.skeleton_from_usage("acme/power.on", contracts.contract_map(catalog))
    assert skeleton["kind"] == "state" and "members" not in skeleton


def test_a_skeleton_of_an_unused_name_is_an_error(catalog):
    with pytest.raises(KeyError, match="not in use"):
        contracts.skeleton_from_usage("nothing", contracts.contract_map(catalog))


# ---- contract rules --------------------------------------------------------------------------------------------------


def test_contract_rules_can_require_definitions_for_a_namespace(catalog):
    defined = {"acme/power.relay": contracts.Definition("acme/power.relay", "capability")}
    violations = contracts.check({"namespaces": ["acme"]}, contracts.contract_map(catalog, definitions=defined))
    assert {v.message for v in violations} == {
        "acme/power.on is in use but has no definition",
        "acme/power.ready is in use but has no definition",
        "acme/bench.rack is in use but has no definition",
        "acme/bench.cabinet is in use but has no definition",
        "acme/bench.lab is in use but has no definition",
    }
    assert {v.rule for v in violations} == {"namespaces"}
    assert contracts.check({"namespaces": ["other"]}, contracts.contract_map(catalog)) == []


def test_contract_rules_can_fix_which_contract_a_role_is(catalog):
    target_files = [
        ("lab1", {"command": "exec.command", "relay": "acme/power.relay"}),
        ("lab2", {"gw.command": "exec.shell"}),
    ]
    violations = contracts.check({"roles": {"command": "exec.command"}}, contracts.contract_map(catalog), target_files)
    assert [(v.rule, v.message) for v in violations] == [
        ("roles", "lab2: role gw.command is exec.shell, the rules say it is always exec.command")
    ]


def test_contract_rules_can_forbid_stabilities(catalog):
    definition = contracts.Definition("acme/power.relay", "capability", stability="deprecated")
    found = contracts.contract_map(catalog, definitions=[definition])
    violations = contracts.check({"forbid_stability": ["deprecated", "experimental"]}, found)
    assert [v.message for v in violations] == ["acme/power.relay is deprecated, which the rules forbid"]


def test_contract_rules_can_require_majors_for_parts_and_tests():
    from score.itf.contracts.usage import ContractEntry

    entry = ContractEntry(
        "acme/relay",
        kind="capability",
        offerers=[("local.relay", ("switch",), None)],
        needers=[("local.panel", "relay", ("switch",), None)],
        tests=[("test_relay", "relay", ("switch",), None)],
    )
    violations = contracts.check({"require_major": ["acme"]}, {entry.name: entry})
    assert len(violations) == 1
    assert violations[0].rule == "require_major"
    assert "local.relay" in violations[0].message
    assert "local.panel" in violations[0].message
    assert "test_relay" in violations[0].message


def test_contract_rules_file_and_unknown_rules(tmp_path, catalog):
    path = tmp_path / "rules.yaml"
    path.write_text("namespaces:\n  - acme\n", encoding="utf-8")
    assert contracts.check(str(path), contracts.contract_map(catalog))
    with pytest.raises(ValueError, match="unknown rule"):
        contracts.check({"colours": []}, {})


def test_roles_of_a_plan_name_scopes(tmp_path):
    from score.itf.core import Session

    plan = (
        Session(
            target="capabilities:\n  platform: localhost.platform\n  command: localhost.exec\nscopes:\n  gw:\n    share:\n      - platform\n",
            plan_only=True,
            run_dir=tmp_path / "run",
        )
        .resolve()
        .target_plan
    )
    assert contracts.roles_of_plan(plan) == {"command": "exec.command", "platform": "platform.instance"}


# ---- conformance -------------------------------------------------------------------------------------------------


def test_conformance_imports_only_modules_for_selected_target_contracts(monkeypatch):
    from types import SimpleNamespace

    from score.itf.contracts import conformance

    check = conformance.Check("relay_switches", lambda node: None)
    imports = []

    def import_module(name):
        assert name == "vendor.conformance", f"unrelated conformance module imported: {name}"
        imports.append(name)
        return SimpleNamespace(CHECKS={"vendor.relay": [check], "vendor.other": [check]})

    monkeypatch.setattr(conformance.importlib, "import_module", import_module)
    definitions = {
        "vendor.relay": contracts.Definition("vendor.relay", "capability", conformance="vendor.conformance"),
        "exec.command": contracts.Definition("exec.command", "capability", conformance="unavailable.conformance"),
    }
    assert conformance.all_checks(definitions, contracts={"vendor.relay"}) == {"vendor.relay": [check]}
    assert imports == ["vendor.conformance"]
    assert conformance.all_checks(definitions, contracts=set()) == {}
    with pytest.raises(AssertionError, match="unrelated conformance module imported"):
        conformance.all_checks(definitions, contracts={"exec.command"})


def test_conformance_checks_are_keyed_by_contract_name_and_found_through_definitions():
    from score.itf.contracts.conformance import all_checks

    checks = all_checks()
    assert {"exec.command", "exec.process", "files.transfer", "platform.instance", "descriptor.endpoint"} <= set(checks)
    assert all(callable(c) for c in checks["exec.command"])


def test_a_namespace_is_the_part_before_the_slash_or_the_first_segment():
    from score.itf.contracts.rules import namespace_of

    assert namespace_of("acme/power.relay") == "acme"
    assert namespace_of("org.example/power.relay") == "org.example"
    assert namespace_of("exec.command") == "exec"
