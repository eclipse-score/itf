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
"""`itf graph`: the topology (roles, factories, slots, scopes, shares) and the bring-up sequence (the goals'
actions in order, with after and breaks, and which steps a probe can skip) as Mermaid, from a resolved plan.
Metadata only: nothing is constructed."""

from __future__ import annotations

import re

from score.itf.core.engine.scopes import ROOT, display


def _id(text: str) -> str:
    return "n_" + re.sub(r"\W", "_", display(text))


def _text(text: str) -> str:
    return display(text).replace('"', "'")


def _node_line(n) -> str:
    label = f"{n.name}<br/>{n.provider}<br/>{n.contract}"
    return f'{_id(n.ref)}["{_text(label)}"]'


def _scope_lines(plan, scope: str) -> list[str]:
    """A subgraph holding the scope's roles and the roles it shares from outside."""
    lines = [f'  subgraph s_{scope}["scope {scope}"]']
    lines += [f"    {_node_line(n)}" for n in plan.nodes if n.scope == scope]
    lines += [
        f'    {_id(alias)}(["{_text(alias.split(".", 1)[1])}<br/>shared"])'
        for alias, _ in plan.aliases
        if alias.startswith(f"{scope}.")
    ]
    return lines + ["  end"]


def topology(session) -> str:
    plan = session.target_plan
    scopes = sorted({n.scope for n in plan.nodes if n.scope != ROOT} | {a.split(".")[0] for a, _ in plan.aliases})
    lines = ["flowchart LR"]
    lines += [f"  {_node_line(n)}" for n in plan.nodes if n.scope == ROOT]
    for scope in scopes:
        lines += _scope_lines(plan, scope)
    return "\n".join(lines + _link_lines(plan))


def _link_lines(plan) -> list[str]:
    """A solid edge per slot binding, a dashed one per share."""
    lines = [f"  {_id(n.ref)} -->|{slot}| {_id(provider)}" for n in plan.nodes for slot, provider in n.bindings]
    return lines + [f"  {_id(alias)} -.->|shares| {_id(target)}" for alias, target in plan.aliases]


def _step_lines(i: int, step, action_label, goals: set) -> list[str]:
    label = f"{i}. {', '.join(step.delivers)}<br/>{action_label(step)}"
    if step.probe:
        lines = [f'  s{i}(["{_text(label + "<br/>probe: skipped when it holds")}"])']
    else:
        lines = [f'  s{i}["{_text(label + "<br/>no probe: always runs")}"]']
    return lines + ([f"  class s{i} goal"] if goals & set(step.delivers) else [])


def _assumed_lines(assumed: str, steps, ids: dict) -> list[str]:
    aid = "a_" + re.sub(r"\W", "_", assumed)
    lines = [f'  {aid}{{{{"assumed: {_text(assumed)}"}}}}']
    return lines + [f"  {aid} -->|after {_text(assumed)}| {ids[s.key]}" for s in steps if assumed in s.requires]


def _edge_line(edge, ids: dict) -> str:
    if edge.reason == "invalidates":
        return f"  {ids[edge.before]} -.->|breaks {_text(edge.state)}| {ids[edge.after]}"
    return f"  {ids[edge.before]} -->|after {_text(edge.state)}| {ids[edge.after]}"


def sequence(session, action_label) -> str:
    plan = session.action_plan
    if plan is None:
        return "flowchart TB"
    ids = {step.key: f"s{i}" for i, step in enumerate(plan.steps, 1)}
    goals = set(plan.goals)
    lines = ["flowchart TB"]
    for i, step in enumerate(plan.steps, 1):
        lines += _step_lines(i, step, action_label, goals)
    for assumed in plan.assumed:
        lines += _assumed_lines(assumed, plan.steps, ids)
    lines += [_edge_line(e, ids) for e in plan.edges if e.before in ids and e.after in ids]
    return "\n".join(lines + (["  classDef goal stroke-width:3px"] if goals else []))


def render_graph(session, kind: str, *, action_label) -> str:
    if kind == "topology":
        return topology(session)
    if kind == "sequence":
        return sequence(session, action_label)
    return "\n".join(
        [
            "```mermaid",
            "%% topology",
            topology(session),
            "```",
            "",
            "```mermaid",
            "%% sequence",
            sequence(session, action_label),
            "```",
        ]
    )
