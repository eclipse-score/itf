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
"""The inventory: what the loaded parts, the tests and the definitions say, as plain data; and pack metadata."""

import importlib.util
from types import SimpleNamespace as NS

from score.itf.contracts import Definition, inventory
from score.itf.contracts.inventory import ObservedRequirement, pack_info


def shape(*names):
    return NS(members=[NS(name=n) for n in names])


def fake_factory(
    label, pack, contract, *members, major=None, needs=(), majors=None, config=None, teardown=False, observes=False
):
    return NS(
        label=label,
        pack=pack,
        contract=contract,
        major=major,
        gives=shape(*members),
        needs=[NS(slot=s, contract=c, expected=shape(*m)) for s, c, m in needs],
        need_majors=majors or {},
        config_schema=NS(describe=lambda: config) if config else None,
        has_teardown=teardown,
        observes=observes,
    )


def fake_action(label, pack, state, *, also=(), probes=(), after=(), breaks=(), probe="", uses=()):
    return NS(
        label=label,
        pack=pack,
        state=state,
        also=list(also),
        extra_probes=list(probes),
        after=list(after),
        breaks=list(breaks),
        probe=probe,
        uses=[NS(slot=s, contract=c, expected=shape(*m)) for s, c, m in uses],
        need_majors={},
    )


CATALOG = NS(
    factories={
        "z": fake_factory(
            "z.late",
            "zp",
            "a.cap",
            "get",
            "put",
            major=2,
            config=[{"name": "n"}],
            teardown=True,
            observes=lambda c: True,
        ),
        "b": fake_factory("b.early", "bp", "a.use", needs=[("s", "a.cap", ("get",))], majors={"s": 2}, observes=True),
    },
    action_descs={
        "act": fake_action(
            "act.on",
            "bp",
            "a.on",
            also=["a.up"],
            probes=["a.warm", "a.up"],
            after=["a.base"],
            breaks=["a.old"],
            probe="p",
            uses=[("s", "a.cap", ("put",))],
        )
    },
    packs=lambda: ["bp", "zp"],
)


def test_the_inventory_lists_factories_and_actions_by_label_with_everything_the_map_shows():
    inv = inventory.inventory(CATALOG, definitions=[], errors=["boom"])
    assert [f["label"] for f in inv["factories"]] == ["b.early", "z.late"]
    early, late = inv["factories"]
    assert early == {
        "label": "b.early",
        "pack": "bp",
        "contract": "a.use",
        "major": None,
        "shape": [],
        "needs": [{"slot": "s", "contract": "a.cap", "expects": ["get"], "major": 2}],
        "config": [],
        "teardown": False,
        "observes": "yes",
    }
    assert late["shape"] == ["get", "put"] and late["config"] == [{"name": "n"}] and late["teardown"] is True
    assert late["observes"] == "when its settings allow" and late["major"] == 2
    (action,) = inv["actions"]
    assert action == {
        "label": "act.on",
        "pack": "bp",
        "state": "a.on",
        "also": ["a.up", "a.warm"],
        "after": ["a.base"],
        "breaks": ["a.old"],
        "probe": True,
        "uses": [{"slot": "s", "contract": "a.cap", "expects": ["put"], "major": None}],
    }
    assert inv["errors"] == ["boom"]


def test_a_factory_that_does_not_observe_says_no():
    inv = inventory.inventory(
        NS(factories={"f": fake_factory("f", "p", "a.cap")}, action_descs={}, packs=lambda: []), definitions=[]
    )
    assert inv["factories"][0]["observes"] == "no"


def test_versioned_action_details_and_contract_map_preserve_each_reference():
    from score.itf.contracts import render

    part = fake_action(
        "local.open",
        "local",
        "shell.open@2",
        also=["shell.ready@3"],
        after=["ecu:platform.up@1"],
        breaks=["ecu:shell.old@4"],
        uses=[("command", "exec.command", ("exec",))],
    )
    part.need_majors["command"] = 2
    catalog = NS(factories={}, action_descs={part.label: part}, packs=lambda: [])
    inv = inventory.inventory(catalog, definitions=[])
    details = inv["actions"][0]
    assert details["state"] == "shell.open@2"
    assert details["also"] == ["shell.ready@3"]
    assert details["after"] == ["ecu:platform.up@1"]
    assert details["breaks"] == ["ecu:shell.old@4"]
    assert details["uses"][0]["major"] == 2
    by_name = {contract["contract"]: contract for contract in inv["contracts"]}
    assert by_name["shell.open"]["offered_by"][0]["major"] == 2
    assert by_name["platform.up"]["needed_by"][0]["major"] == 1
    assert by_name["shell.old"]["needed_by"][0]["slot"] == "breaks"
    page = render.render_html(inv)
    for token in ("shell.open@2", "shell.ready@3", "ecu:platform.up@1", "ecu:shell.old@4", "exec.command@2"):
        assert token in page
    assert "requires platform.up@1" in page
    assert "(breaks) @4" in render.render_text(inv)


def test_each_pack_lists_the_labels_of_its_factories_and_actions():
    inv = inventory.inventory(CATALOG, definitions=[])
    assert [(p["name"], p["factories"], p["actions"]) for p in inv["packs"]] == [
        ("bp", ["b.early"], ["act.on"]),
        ("zp", ["z.late"], []),
    ]
    named = inventory.inventory(CATALOG, definitions=[], packs=["zp"])
    assert [p["name"] for p in named["packs"]] == ["zp"]


def test_contracts_carry_their_definition_the_tests_and_the_disagreements():
    definition = Definition(
        "a.cap", "capability", version=1, summary="S", role="r", see_also=("a.use",), guarantees=("g",), source="x.yaml"
    )
    tests = [("t::x", ObservedRequirement("r", "a.cap", ("get", "zap")))]
    inv = inventory.inventory(CATALOG, definitions=[definition], tests=tests)
    by_name = {c["contract"]: c for c in inv["contracts"]}
    cap = by_name["a.cap"]
    assert cap["tests"] == [{"test": "t::x", "role": "r", "shape": ["get", "zap"], "major": None}]
    assert cap["definition"] == {
        "version": 1,
        "kind": "capability",
        "summary": "S",
        "description": "",
        "role": "r",
        "stability": "stable",
        "replaced_by": None,
        "conformance": None,
        "see_also": ["a.use"],
        "probe": None,
        "guarantees": ["g"],
        "members": [],
        "source": "x.yaml",
    }
    assert cap["defined"] is True and cap["checks"] == []
    assert [(d["kind"], d["message"]) for d in cap["disagreements"]] == [
        ("missing-member", "test t::x requires a.cap.zap, which no offerer has"),
        ("major-mismatch", "z.late offers a.cap@2, but the definition's version is 1"),
    ]
    assert by_name["a.use"]["definition"] is None and by_name["a.use"]["defined"] is False
    assert [c["contract"] for c in inv["contracts"]] == sorted(by_name)


def test_pack_info_reads_version_prerequisites_and_the_first_paragraph_of_the_readme():
    info = pack_info("ping")
    assert info["name"] == "ping" and info["version"] == "0.1.0"
    assert info["prerequisites"] and info["summary"] and "\n" not in info["summary"]


def test_pack_info_of_an_unknown_pack_is_empty():
    assert pack_info("no_such_pack") == {"name": "no_such_pack", "version": "", "prerequisites": [], "summary": ""}


def _pack_at(monkeypatch, directory):
    spec = NS(submodule_search_locations=[str(directory)])
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: spec)


def test_pack_info_skips_the_license_comment_and_headings_and_joins_the_first_paragraph(tmp_path, monkeypatch):
    (tmp_path / "pack.yaml").write_text("name: x\nversion: 3\nprerequisites:\n  - one\n  - 2\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "<!--\nlicense\n-->\n# Title\n\n**bold lead**\n\nFirst line\n  second line\n\nNot this one.\n", encoding="utf-8"
    )
    _pack_at(monkeypatch, tmp_path)
    assert pack_info("x") == {
        "name": "x",
        "version": "3",
        "prerequisites": ["one", "2"],
        "summary": "First line second line",
    }


def test_pack_info_tolerates_an_empty_pack_yaml_and_a_missing_readme(tmp_path, monkeypatch):
    (tmp_path / "pack.yaml").write_text("", encoding="utf-8")
    _pack_at(monkeypatch, tmp_path)
    assert pack_info("x") == {"name": "x", "version": "", "prerequisites": [], "summary": ""}


def test_pack_info_of_a_directory_with_neither_file_is_empty(tmp_path, monkeypatch):
    _pack_at(monkeypatch, tmp_path)
    assert pack_info("x")["version"] == "" and pack_info("x")["summary"] == ""


def test_requirements_are_read_from_decorators_without_importing_the_test(tmp_path):
    test = tmp_path / "test_x.py"
    test.write_text(
        "import itf\n\n"
        "@itf.requires('relay', 'acme/power.relay@2', ['switch', 'read'])\n"
        "def test_a(): ...\n\n"
        "@itf.requires('cam', contract='acme/cam', shape=['frame'], scope='lab')\n"
        "class TestB: ...\n\n"
        "@requires('bare')\n"
        "def test_c(): ...\n\n"
        "@itf.requires(1)\n"
        "def test_d(): ...\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text("def (:\n", encoding="utf-8")
    found = inventory.collect_requirements([tmp_path, tmp_path / "missing.py"])
    assert [(i.split("::")[1], r) for i, r in found] == [
        ("test_a", ObservedRequirement("relay", "acme/power.relay", ("switch", "read"), None, 2)),
        ("TestB", ObservedRequirement("cam", "acme/cam", ("frame",), "lab", None)),
        ("test_c", ObservedRequirement("bare", None, (), None)),
    ]


def test_strict_protocol_requirements_are_read_without_importing_the_test(tmp_path):
    test = tmp_path / "test_strict.py"
    test.write_text(
        "from typing import Protocol\nimport score.itf as itf\n"
        "raise RuntimeError('must not import')\n"
        "class BaseAPI(Protocol):\n"
        "    __contract__ = 'exec.command@2'\n"
        "    def exec(self, command: str) -> str: ...\n"
        "class CommandAPI(BaseAPI, Protocol):\n"
        "    status: str\n"
        "    def _private(self): ...\n"
        "itf_requires = itf.requires('module_command', shape=CommandAPI)\n"
        "@itf.requires('command', shape=CommandAPI)\n"
        "def test_command(): ...\n",
        encoding="utf-8",
    )
    errors = []
    found = inventory.collect_requirements([test], errors=errors)
    assert errors == []
    assert [requirement for _, requirement in found] == [
        ObservedRequirement("module_command", "exec.command", ("exec", "status"), major=2),
        ObservedRequirement("command", "exec.command", ("exec", "status"), major=2),
    ]


def test_protocol_import_aliases_are_resolved_without_importing_the_test(tmp_path):
    imports = [
        ("from typing import Protocol as TypingProtocol", "TypingProtocol"),
        ("from typing_extensions import Protocol as TypingProtocol", "TypingProtocol"),
        ("import typing as types", "types.Protocol"),
        ("import typing_extensions as types", "types.Protocol"),
    ]
    for statement, base in imports:
        test = tmp_path / "test_alias.py"
        test.write_text(
            f"{statement}\nimport score.itf as itf\n"
            "raise RuntimeError('must not import')\n"
            f"class BaseAPI({base}):\n"
            "    __contract__ = 'exec.command@2'\n"
            "    def exec(self, command: str) -> bytes: ...\n"
            f"class CommandAPI(BaseAPI, {base}):\n"
            "    status: str\n"
            "itf_requires = itf.requires('module_command', shape=CommandAPI)\n"
            "@itf.requires('command', shape=CommandAPI)\n"
            "def test_command(): ...\n",
            encoding="utf-8",
        )
        errors = []
        found = inventory.collect_requirements([test], errors=errors)
        assert errors == [], statement
        assert [requirement for _, requirement in found] == [
            ObservedRequirement("module_command", "exec.command", ("exec", "status"), major=2),
            ObservedRequirement("command", "exec.command", ("exec", "status"), major=2),
        ]


def test_unresolved_protocol_shapes_are_explicit_inventory_errors(tmp_path, caplog):
    test = tmp_path / "test_imported.py"
    test.write_text(
        "from consumer import CommandAPI\nimport score.itf as itf\n"
        "@itf.requires('command', shape=CommandAPI)\ndef test_command(): ...\n",
        encoding="utf-8",
    )
    errors = []
    inventory.collect_requirements([test], errors=errors)
    assert len(errors) == 1
    assert str(test) in errors[0] and "cannot statically resolve Protocol shape CommandAPI" in errors[0]
    inventory.collect_requirements([test])
    assert errors[0] in caplog.text
