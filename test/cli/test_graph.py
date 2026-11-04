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
"""`itf graph` from hand-made plans: every line of the Mermaid text is traceable to one field."""

from __future__ import annotations

from types import SimpleNamespace as NS

from score.itf.cli.graph import render_graph, sequence, topology
from score.itf.core.engine.scopes import ROOT


def node(scope, name, provider="p.x", contract="c.x", bindings=()):
    ref = name if scope == ROOT else f"{scope}.{name}"
    return NS(scope=scope, name=name, ref=ref, provider=provider, contract=contract, bindings=tuple(bindings))


def step(key, delivers, probe="", requires=()):
    return NS(key=key, delivers=tuple(delivers), probe=probe, requires=tuple(requires))


def edge(before, after, state, reason="delivers-requires"):
    return NS(before=before, after=after, state=state, reason=reason)


def label_of(step):
    return f"act.{step.key}"


def session(nodes=(), aliases=(), plan=None):
    return NS(target_plan=NS(nodes=tuple(nodes), aliases=tuple(aliases)), action_plan=plan)


def test_topology_puts_root_roles_first_then_a_subgraph_per_scope_with_its_roles_and_shares():
    s = session(
        nodes=[
            node(ROOT, "platform", "sim.platform", "platform.instance"),
            node("gw", "command", "sim.exec", "exec.command", [("platform", "platform")]),
        ],
        aliases=[("gw.platform", "platform")],
    )
    assert topology(s).splitlines() == [
        "flowchart LR",
        '  n_platform["platform<br/>sim.platform<br/>platform.instance"]',
        '  subgraph s_gw["scope gw"]',
        '    n_gw_command["command<br/>sim.exec<br/>exec.command"]',
        '    n_gw_platform(["platform<br/>shared"])',
        "  end",
        "  n_gw_command -->|platform| n_platform",
        "  n_gw_platform -.->|shares| n_platform",
    ]


def test_topology_lists_scopes_sorted_including_those_that_only_share_and_quotes_become_apostrophes():
    s = session(
        nodes=[node("zeta", "a", 'p."q"')],
        aliases=[("alpha.shared", "zeta.a")],
    )
    lines = topology(s).splitlines()
    assert [ln for ln in lines if "subgraph" in ln] == [
        '  subgraph s_alpha["scope alpha"]',
        '  subgraph s_zeta["scope zeta"]',
    ]
    assert "p.'q'" in "\n".join(lines) and 'p."q"' not in "\n".join(lines)
    assert '    n_alpha_shared(["shared<br/>shared"])' in lines


def test_a_target_file_without_roles_is_just_the_header():
    assert topology(session()) == "flowchart LR"


def test_sequence_numbers_the_steps_marks_probes_and_goals_and_draws_after_and_breaks_edges():
    plan = NS(
        steps=(step("x", ["a:x"]), step("y", ["a:y", "a:y2"], probe="m:p")),
        goals=("a:y",),
        assumed=(),
        edges=(
            edge("x", "y", "a:x"),
            edge("y", "x", "a:y", "invalidates"),
            edge("x", "elsewhere", "a:z"),
        ),
    )
    assert sequence(session(plan=plan), label_of).splitlines() == [
        "flowchart TB",
        '  s1["1. a:x<br/>act.x<br/>no probe: always runs"]',
        '  s2(["2. a:y, a:y2<br/>act.y<br/>probe: skipped when it holds"])',
        "  class s2 goal",
        "  s1 -->|after a:x| s2",
        "  s2 -.->|breaks a:y| s1",
        "  classDef goal stroke-width:3px",
    ]


def test_an_assumed_state_is_drawn_as_a_hexagon_pointing_at_the_steps_that_require_it():
    plan = NS(
        steps=(step("x", ["a:x"], requires=["a:given"]), step("y", ["a:y"])),
        goals=(),
        assumed=("a:given",),
        edges=(),
    )
    lines = sequence(session(plan=plan), label_of).splitlines()
    assert '  a_a_given{{"assumed: a:given"}}' in lines
    assert "  a_a_given -->|after a:given| s1" in lines
    assert not any("s2" in ln and "a_a_given" in ln for ln in lines)
    assert "classDef goal stroke-width:3px" not in "\n".join(lines)


def test_without_an_action_plan_the_sequence_is_just_the_header():
    assert sequence(session(plan=None), label_of) == "flowchart TB"


def test_render_graph_picks_one_graph_or_both_in_fenced_blocks():
    s = session(nodes=[node(ROOT, "a")], plan=NS(steps=(), goals=(), assumed=(), edges=()))
    assert render_graph(s, "topology", action_label=label_of) == topology(s)
    assert render_graph(s, "sequence", action_label=label_of) == sequence(s, label_of)
    both = render_graph(s, "both", action_label=label_of)
    assert both == "\n".join(
        ["```mermaid", "%% topology", topology(s), "```", "", "```mermaid", "%% sequence", sequence(s, label_of), "```"]
    )
