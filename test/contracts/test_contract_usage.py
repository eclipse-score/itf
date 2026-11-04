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
"""The contract map from plain descriptors: what each kind of part contributes and each disagreement it reads.

Descriptors here are bare objects with the attributes the map reads, so every case is one line of input and
one line of expectation (the loaded-pack cases live in test_contract_library.py).
"""

from types import SimpleNamespace as NS

from pathlib import Path

import pytest

from score.itf.contracts import Definition, Member, contract_map, skeleton_from_usage


def need(slot, contract, *members):
    return NS(slot=slot, contract=contract, expected=list(members))


def factory(label, contract, *members, major=None, needs=(), majors=None):
    return NS(
        label=label, contract=contract, gives=list(members), major=major, needs=list(needs), need_majors=majors or {}
    )


def action(label, state, *, also=(), after=(), breaks=(), uses=(), majors=None):
    return NS(
        label=label,
        state=state,
        also=list(also),
        after=list(after),
        breaks=list(breaks),
        uses=list(uses),
        need_majors=majors or {},
    )


def messages(entry, kind=None):
    return [d.message for d in entry.disagreements if kind in (None, d.kind)]


def test_a_factory_offers_its_contract_with_the_public_members_it_publishes_and_needs_others():
    found = contract_map(
        [factory("f", "a.cap", "put", "_private", "get", major=2, needs=[need("db", "a.db", "q")], majors={"db": 3})]
    )
    assert found["a.cap"].offerers == [("f", ("get", "put"), 2)]  # sorted, without the underscored member
    assert found["a.db"].needers == [("f", "db", ("q",), 3)]
    assert list(found) == ["a.cap", "a.db"]  # sorted by name


def test_an_action_offers_its_state_and_the_ones_it_also_makes_true_and_needs_those_it_comes_after():
    found = contract_map(
        [
            action(
                "act",
                "a.on",
                also=["a.up"],
                after=["scope:a.ready", "a.base"],
                uses=[need("r", "a.cap", "m")],
                majors={"r": 1},
            )
        ]
    )
    assert found["a.on"].kind == "state" and found["a.on"].offerers == [("act", (), None)]
    assert found["a.up"].offerers == [("act", (), None)]
    assert found["a.ready"].needers == [("act", "after", (), None)]  # "scope:" is dropped
    assert found["a.base"].needers == [("act", "after", (), None)]
    assert found["a.cap"].kind == "capability" and found["a.cap"].needers == [("act", "r", ("m",), 1)]


def test_a_catalog_is_read_through_its_factories_and_actions():
    catalog = NS(factories={"f": factory("f", "a.cap")}, action_descs={"act": action("act", "a.on")})
    assert list(contract_map(catalog)) == ["a.cap", "a.on"]


def test_tests_are_listed_with_or_without_an_id_and_a_requirement_with_no_contract_is_ignored():
    parts = [factory("f", "a.cap", "m")]
    tests = [
        ("t::x", NS(role="r", contract="a.cap", shape=("m",))),
        NS(role="bare", contract="a.cap", shape=None),
        ("t::y", NS(role="loose", contract=None, shape=())),
    ]
    assert contract_map(parts, tests=tests)["a.cap"].tests == [("t::x", "r", ("m",), None), ("", "bare", (), None)]
    assert list(contract_map([], tests=tests)) == ["a.cap"]


def test_a_state_name_that_a_capability_also_uses_becomes_a_state():
    found = contract_map([factory("f", "a.x"), action("act", "a.x")])
    assert found["a.x"].kind == "state"


def test_a_definition_gives_the_name_its_kind_and_the_first_one_wins():
    one, two = Definition("a.on", "state", source="1"), Definition("a.on", "state", source="2")
    by_list = contract_map([], definitions=[one, two])["a.on"]
    assert (by_list.kind, by_list.definition, by_list.definitions) == ("state", one, [one, two])
    assert contract_map([], definitions={"a.on": two})["a.on"].definition is two


def test_a_member_nobody_offers_is_a_disagreement_only_when_something_offers_the_contract():
    needers = [factory("c", "a.use", needs=[need("s", "a.cap", "get", "zap")])]
    tests = [("t::x", NS(role="r", contract="a.cap", shape=("zap",)))]
    none_offered = contract_map(needers, tests=tests)["a.cap"]
    assert none_offered.disagreements == []
    found = contract_map([factory("f1", "a.cap", "get"), factory("f2", "a.cap", "put"), *needers], tests=tests)["a.cap"]
    assert messages(found) == [
        "c (slot s) expects a.cap.zap, which no offerer has (f1, f2)",
        "test t::x requires a.cap.zap, which no offerer has",
    ]
    anonymous = contract_map([factory("f", "a.cap")], tests=[NS(role="who", contract="a.cap", shape=("m",))])
    assert messages(anonymous["a.cap"]) == ["test who requires a.cap.m, which no offerer has"]


def test_a_needed_major_nobody_offers_is_a_disagreement_and_unversioned_ones_agree_with_anything():
    parts = [
        factory("f1", "a.cap", major=1),
        factory("f2", "a.cap", major=3),
        factory("n1", "a.n1", needs=[need("s", "a.cap")], majors={"s": 2}),
        factory("n2", "a.n2", needs=[need("s", "a.cap")]),
        factory("n3", "a.n3", needs=[need("s", "a.cap")], majors={"s": 3}),
    ]
    assert messages(contract_map(parts)["a.cap"]) == ["n1 (slot s) expects a.cap@2, offered: @1, @3"]
    assert contract_map(parts[2:3])["a.cap"].disagreements == []  # nobody offers: nothing to disagree with


def test_a_definition_requires_its_required_members_and_a_version_no_lower_than_the_offered_major():
    definition = Definition(
        "a.cap", "capability", version=1, members=(Member("must"), Member("may", required=False), Member("get"))
    )
    parts = [
        factory("f1", "a.cap", "get", major=1),
        factory("f2", "a.cap", "get", "must", major=4),
        factory("f3", "a.cap"),
    ]
    entry = contract_map(parts, definitions=[definition])["a.cap"]
    assert messages(entry, "missing-definition-member") == [
        "f1 offers a.cap without must, which its definition requires",
        "f3 offers a.cap without must, which its definition requires",
        "f3 offers a.cap without get, which its definition requires",
    ]
    assert messages(entry, "major-mismatch") == ["f2 offers a.cap@4, but the definition's version is 1"]


def test_an_unversioned_state_definition_does_not_check_members_or_versions():
    entry = contract_map([action("act", "a.on")], definitions=[Definition("a.on", "state", version=0)])["a.on"]
    assert entry.disagreements == []


def test_state_offers_dependencies_and_breaks_share_a_base_name_and_preserve_majors():
    found = contract_map(
        [
            action("open", "shell.open@2", also=["shell.ready@3"]),
            action("close", "shell.closed@1", after=["ecu:shell.open@1"], breaks=["ecu:shell.ready@3"]),
        ],
        definitions=[Definition("shell.open", "state", version=1)],
    )
    assert set(found) == {"shell.open", "shell.ready", "shell.closed"}
    assert found["shell.open"].offerers == [("open", (), 2)]
    assert found["shell.open"].needers == [("close", "after", (), 1)]
    assert found["shell.ready"].offerers == [("open", (), 3)]
    assert found["shell.ready"].needers == [("close", "breaks", (), 3)]
    assert messages(found["shell.open"], "major-mismatch") == [
        "close (slot after) expects shell.open@1, offered: @2",
        "open offers shell.open@2, but the definition's version is 1",
    ]
    assert skeleton_from_usage("shell.ready", found)["version"] == 3


def test_require_major_rules_cover_unversioned_state_offers_and_references():
    from score.itf.contracts.rules import check

    found = contract_map(
        [
            action("open", "shell.open", also=["shell.ready@2"]),
            action("close", "other.closed", after=["shell.ready"], breaks=["shell.open"]),
        ]
    )
    violations = check({"require_major": ["shell"]}, found)
    assert [violation.message for violation in violations] == [
        "shell.open requires explicit @major declarations for: close, open",
        "shell.ready requires explicit @major declarations for: close",
    ]
    assert check({"require_major": ["shell"]}, contract_map([action("open", "shell.open@2")])) == []


def test_two_definitions_name_where_each_came_from():
    entry = contract_map(
        [], definitions=[Definition("a.cap", "capability", source="x.yaml"), Definition("a.cap", "capability")]
    )["a.cap"]
    assert messages(entry, "two-definitions") == ["a.cap is defined 2 times: x.yaml, ?"]


def test_the_entry_serialises_what_it_found():
    entry = contract_map(
        [factory("f", "a.cap", "m", major=1), factory("n", "a.n", needs=[need("s", "a.cap", "z")])],
        tests=[("t", NS(role="r", contract="a.cap", shape=("m",)))],
    )["a.cap"]
    assert entry.to_json() == {
        "contract": "a.cap",
        "kind": "capability",
        "offered_by": [{"label": "f", "shape": ["m"], "major": 1}],
        "needed_by": [{"label": "n", "slot": "s", "expects": ["z"], "major": None}],
        "tests": [{"test": "t", "role": "r", "shape": ["m"], "major": None}],
        "defined": False,
        "disagreements": [
            {"kind": "missing-member", "message": "n (slot s) expects a.cap.z, which no offerer has (f)"}
        ],
    }


def test_a_skeleton_lists_expected_members_first_then_published_ones_as_optional():
    parts = [
        factory("f", "a.cap", "pub", "shared", major=2),
        factory("n", "a.n", needs=[need("s", "a.cap", "shared", "want")], majors={"s": 3}),
    ]
    tests = [
        ("t1", NS(role="zeta", contract="a.cap", shape=("tested",))),
        ("t2", NS(role="alpha", contract="a.cap", shape=())),
    ]
    skeleton = skeleton_from_usage("a.cap", contract_map(parts, tests=tests))
    assert skeleton == {
        "contract": "a.cap",
        "kind": "capability",
        "version": 3,
        "summary": "TODO",
        "description": "TODO",
        "role": "alpha",
        "members": [
            {"name": "shared", "signature": "TODO", "semantics": "TODO"},
            {"name": "tested", "signature": "TODO", "semantics": "TODO"},
            {"name": "want", "signature": "TODO", "semantics": "TODO"},
            {"name": "pub", "signature": "TODO", "semantics": "TODO", "required": False},
        ],
        "guarantees": ["TODO"],
    }


def test_a_skeleton_with_nothing_observed_has_version_one_and_no_role_or_members():
    skeleton = skeleton_from_usage("a.cap", contract_map([factory("f", "a.cap")]))
    assert skeleton["version"] == 1 and "role" not in skeleton and "members" not in skeleton
    state = skeleton_from_usage("a.on", contract_map([action("act", "a.on")]))
    assert state["kind"] == "state" and set(state) == {
        "contract",
        "kind",
        "version",
        "summary",
        "description",
        "guarantees",
    }


def test_a_skeleton_of_an_unused_name_lists_what_is_in_use():
    with pytest.raises(KeyError, match="'x' is not in use; contracts in use: a.cap"):
        skeleton_from_usage("x", contract_map([factory("f", "a.cap")]))
    with pytest.raises(KeyError, match=r"\(none\)"):
        skeleton_from_usage("x", {})


def test_requirements_on_a_class_and_on_a_module_are_read_without_importing(tmp_path):
    from score.itf.contracts import inventory

    (tmp_path / "test_scoped.py").write_text(
        "import score.itf as itf\n\nitf_requires = [itf.requires('files', contract='files.transfer')]\n\n\n"
        "@itf.requires('command')\nclass TestA:\n    def test_x(self, target): ...\n"
    )
    found = {(Path(test.split("::")[-1]).name, r.role) for test, r in inventory.collect_requirements([tmp_path])}
    assert found == {("test_scoped.py", "files"), ("TestA", "command")}
