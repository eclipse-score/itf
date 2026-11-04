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
"""`itf diff OLD NEW`: what a reader is told when two plan files differ."""

from __future__ import annotations

import json

from score.itf.cli.main import main


def node(scope, name, provider="p.a", **extra):
    return {"scope": scope, "name": name, "provider": provider, **extra}


def step(key, **extra):
    return {"key": key, "impl": f"m:{key}", "delivers": [key], **extra}


def plan(nodes=(), steps=(), scopes=None, **extra):
    target = {"nodes": list(nodes)}
    if scopes is not None:
        target["scopes"] = scopes
    return {"target": target, "action": {"steps": list(steps)}, **extra}


def diff(tmp_path, capsys, old, new):
    (tmp_path / "old.json").write_text(json.dumps(old), encoding="utf-8")
    (tmp_path / "new.json").write_text(json.dumps(new), encoding="utf-8")
    capsys.readouterr()
    code = main(["diff", str(tmp_path / "old.json"), str(tmp_path / "new.json")])
    return code, capsys.readouterr().out.splitlines()


def test_identical_plans_say_so_and_exit_zero(tmp_path, capsys):
    same = plan([node("t", "a")], [step("x")])
    assert diff(tmp_path, capsys, same, same) == (0, ["plans are identical"])


def test_added_and_removed_roles_name_their_factory(tmp_path, capsys):
    old = plan([node("t", "gone", "p.old"), node("t", "kept")])
    new = plan([node("t", "kept"), node("t", "fresh", "p.new")])
    assert diff(tmp_path, capsys, old, new) == (1, ["+ role t.fresh  (p.new)", "- role t.gone  (p.old)"])


def test_a_changed_role_lists_each_changed_field_down_into_nested_ones(tmp_path, capsys):
    old = plan([node("t", "a", "p.a", config={"port": 1, "tls": {"on": False}}, contract="c.x")])
    new = plan([node("t", "a", "p.b", config={"port": 2, "tls": {"on": True}, "new": "x"}, contract="c.x")])
    assert diff(tmp_path, capsys, old, new) == (
        1,
        [
            "~ role t.a",
            '      config.new: null -> "x"',
            "      config.port: 1 -> 2",
            "      config.tls.on: false -> true",
            '      provider: "p.a" -> "p.b"',
        ],
    )


def test_roles_of_every_scope_are_compared_by_scope_and_name(tmp_path, capsys):
    old = plan([node("root", "r")], scopes={"gw": {"nodes": [node("gw", "x", "p.1")]}})
    new = plan([node("root", "r")], scopes={"gw": {"nodes": [node("gw", "x", "p.2"), node("gw", "y", "p.3")]}})
    assert diff(tmp_path, capsys, old, new) == (
        1,
        ["+ role gw.y  (p.3)", "~ role gw.x", '      provider: "p.1" -> "p.2"'],
    )


def test_added_removed_and_changed_steps_are_listed_in_that_order(tmp_path, capsys):
    old = plan(steps=[step("gone"), step("same"), step("changed", requires=["a"])])
    new = plan(steps=[step("same"), step("changed", requires=["b"]), step("fresh")])
    assert diff(tmp_path, capsys, old, new) == (
        1,
        [
            "+ step fresh",
            "- step gone",
            "~ step changed",
            '      requires: ["a"] -> ["b"]',
        ],
    )


def test_a_step_without_a_key_is_identified_by_its_action_and_what_it_delivers(tmp_path, capsys):
    old = plan(steps=[{"impl": "m:f", "delivers": ["a", "b"]}])
    new = plan(steps=[{"impl": "m:f", "delivers": ["a", "b"], "probe": "m:p"}])
    assert diff(tmp_path, capsys, old, new) == (
        1,
        ["~ step m:f:a,b", '      probe: null -> "m:p"'],
    )


def test_the_same_steps_in_another_order_are_reported_as_reordered(tmp_path, capsys):
    old = plan(steps=[step("a"), step("b"), step("c")])
    new = plan(steps=[step("c"), step("a"), step("b"), step("new")])
    assert diff(tmp_path, capsys, old, new) == (
        1,
        ["+ step new", "~ steps reordered:", "      was a -> b -> c", "      now c -> a -> b"],
    )


def test_changed_assumptions_are_reported_and_equal_ones_are_not(tmp_path, capsys):
    assert diff(tmp_path, capsys, plan(assumptions=["a"]), plan(assumptions=["a"])) == (0, ["plans are identical"])
    assert diff(tmp_path, capsys, plan(assumptions=["a"]), plan(assumptions=["b"])) == (1, ["~ assumptions changed"])


def test_a_plan_without_a_target_or_an_action_is_an_empty_plan(tmp_path, capsys):
    assert diff(tmp_path, capsys, {}, plan([node("t", "a")], [step("x")])) == (
        1,
        ["+ role t.a  (p.a)", "+ step x"],
    )


def test_an_unreadable_plan_file_is_a_usage_error(tmp_path, capsys):
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert main(["diff", str(tmp_path / "bad.json"), str(tmp_path / "bad.json")]) == 2
    assert capsys.readouterr().err.startswith("itf: ")
    assert main(["diff", str(tmp_path / "missing.json"), str(tmp_path / "bad.json")]) == 2
