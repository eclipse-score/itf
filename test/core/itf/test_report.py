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
"""The HTML report a reader gets in the run directory: what each scope shows, and what a failure shows.

Every test renders a small plan through `render_target_html` (the entry point `write_artifacts` uses) and
asserts on what the page says: the cards, the scope headings, the wanted/missing lane, the data behind
the hover panel.
"""

import json
import re
from dataclasses import dataclass

from score.itf.core import ResolutionFailed
from score.itf.core.engine.bringup import RunReport
from score.itf.core.engine.report import render_target_html
from score.itf.core.octo import (
    CapabilityContractClaim,
    GoalClaim,
    Need,
    NodeClaim,
    ProviderClaim,
    Shape,
    StateContractClaim,
    resolve_actions,
    resolve_target,
)

ENDPOINT = "itf.capabilities.descriptor.endpoint"


def target_plan():
    """shop: ep, pool (needs ep, gets lab.gw: another scope), cache (needs pool); lab: gw; shop.main aliases pool."""
    claims = frozenset(
        {
            CapabilityContractClaim(token=ENDPOINT, gives=Shape.of("host")),
            CapabilityContractClaim(token="db.pool", gives=Shape.of("query")),
            CapabilityContractClaim(token="cache.client", gives=Shape.of("get")),
            ProviderClaim(name="acme.endpoint", implements=ENDPOINT, impl="m:endpoint"),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(Need(slot="endpoint", contract=ENDPOINT, expected=Shape.of("host")),),
            ),
            ProviderClaim(
                name="acme.cache",
                implements="cache.client",
                impl="m:cache",
                needs=(Need(slot="pool", contract="db.pool", expected=Shape.of("query")),),
            ),
            NodeClaim(scope="shop", name="ep", contract=ENDPOINT, using="acme.endpoint"),
            NodeClaim(
                scope="lab", name="gw", contract=ENDPOINT, using="acme.endpoint", config=(("port", 8), ("tls", None))
            ),
            NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool", bind=(("endpoint", "lab.gw"),)),
            NodeClaim(scope="shop", name="cache", contract="cache.client", using="acme.cache"),
            NodeClaim(scope="shop", name="main", alias="shop.pool"),
        }
    )
    result = resolve_target(claims)
    assert result.ok(), result.diagnostics
    return result.plan


STATES = (
    StateContractClaim(
        token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop", uses=(Need("db", "db.pool", Shape.of("query")),)
    ),
    StateContractClaim(
        token="schema", impl="m:schema", probe="m:p_schema", scope="shop", requires=frozenset({"db_up"})
    ),
    StateContractClaim(
        token="served",
        impl="m:serve",
        scope="shop",
        requires=frozenset({"schema"}),
        uses=(Need("client", "cache.client", Shape.of("get")),),
    ),
    StateContractClaim(
        token="lit", impl="m:lit", probe="m:p_lit", scope="lab", uses=(Need("gw", ENDPOINT, Shape.of("host")),)
    ),
)
GOALS = (GoalClaim(scope="shop", states=frozenset({"served"})), GoalClaim(scope="lab", states=frozenset({"lit"})))


def action_plan(target, **options):
    result = resolve_actions(frozenset(STATES + GOALS), target, **options)
    assert result.ok(), result.diagnostics
    return result.plan


def items_of(page: str) -> dict:
    """The data behind the hover panel, as the page embeds it."""
    return json.loads(re.search(r'id="itf-data">(.*?)</script>', page, re.S).group(1).replace("\\u003c", "<"))["items"]


def scopes_of(page: str) -> list[str]:
    return re.findall(r'<section class="scope"><div class="scope-h"><h2>([^<]*)</h2>', page)


def cards_of(page: str, kind: str) -> list[str]:
    return re.findall(rf'<g class="item {kind}[^"]*" data-id="([^"]*)"', page)


def test_a_resolved_plan_draws_every_scope_with_its_bring_up_lane_and_target_file_tree():
    target = target_plan()
    page = render_target_html(target, action_plan(target), title="itf target · demo")
    assert "<title>itf target · demo</title>" in page and "<h1>itf target · demo</h1>" in page
    assert scopes_of(page) == ["lab", "shop"]
    assert "2 scope(s)" in page and "4 capabilities" in page
    assert "BRING-UP ORDER" in page and "TARGET_FILE" in page and "WANTED" not in page
    assert page.count("TARGET</text>") == 2
    # the steps of the shop scope are numbered in execution order
    shop_steps = [s for s in cards_of(page, "state") if s.startswith("s|shop:")]
    assert shop_steps == ["s|shop:db_up", "s|shop:schema", "s|shop:served"]
    assert 'class="idx">3</tspan>' in page
    # the lab scope reaches into nothing: its node is a plain card; the shop's pool reaches lab.gw as external
    assert "n|shop.cache" in cards_of(page, "node") and "n|lab.gw" in cards_of(page, "node external")
    assert "in scope lab" in page


def test_the_scope_heading_counts_what_the_scope_holds():
    target = target_plan()
    page = render_target_html(target, action_plan(target))
    metas = re.findall(r'<span class="meta">([^<]*)</span>', page)
    assert metas == [
        "1 capabilities · 1 bring-up steps · 1 level(s) deep",
        "3 capabilities · 3 bring-up steps · 3 level(s) deep",
    ]


def test_the_tree_links_a_consumer_to_what_it_consumes_labelled_by_slot_and_the_target_to_the_top_of_each_scope():
    target = target_plan()
    page = render_target_html(target, action_plan(target))
    links = re.findall(r'<g class="link ([^"]*)" data-a="([^"]*)" data-b="([^"]*)">', page)
    assert ("tree root", "t|shop", "n|shop.cache") in links
    assert ("tree", "n|shop.cache", "n|shop.pool") in links
    assert ("tree", "n|shop.pool", "n|lab.gw") in links
    assert ("flow", "s|shop:db_up", "s|shop:schema") in links
    assert ("uses", "s|shop:served", "n|shop.cache") in links
    assert ("uses", "s|lab:lit", "n|lab.gw") in links
    # the slot name rides on the link between consumer and consumed
    assert ">pool</text>" in page and ">endpoint</text>" in page
    # `ep` is consumed by nothing and used by nothing: it hangs from the target directly
    assert ("tree root", "t|shop", "n|shop.ep") in links


def test_the_hover_data_of_a_capability_says_why_it_was_chosen_and_how_each_slot_was_bound():
    target = target_plan()
    pool = items_of(render_target_html(target, action_plan(target)))["n|shop.pool"]
    assert (pool["kind"], pool["title"], pool["contract"], pool["provider"]) == ("node", "pool", "db.pool", "acme.pool")
    assert pool["why_provider"] == "named by the target file"
    (slot,) = pool["slots"]
    assert (slot["id"], slot["slot"], slot["expected"], slot["given"], slot["missing"]) == (
        "n|lab.gw",
        "endpoint",
        ["host"],
        ["host"],
        [],
    )
    assert slot["why"] == "bound by the target file (bind:)"
    assert [c["id"] for c in pool["consumed_by"]] == ["n|shop.cache"]
    assert [(u["id"], u["slot"]) for u in pool["used_by"]] == [("s|shop:db_up", "db")]
    assert "t|shop" not in pool["related"] and "n|shop.cache" in pool["related"]
    gw = items_of(render_target_html(target, action_plan(target)))["n|lab.gw"]
    assert gw["config"] == [["port", "8"], ["tls", "null"]]
    assert "t|lab" in gw["related"]  # nothing in lab consumes it: it hangs from the target


def test_the_hover_data_of_a_state_carries_order_status_uses_and_the_edges_around_it():
    target = target_plan()
    plan = action_plan(target)
    items = items_of(render_target_html(target, plan))
    schema = items["s|shop:schema"]
    assert (schema["kind"], schema["title"], schema["order"], schema["total"]) == ("state", "schema", 2, 3)
    assert schema["status"] == "planned" and schema["status_text"] == "planned"
    assert [a["id"] for a in schema["after"]] == ["s|shop:db_up"] and [b["id"] for b in schema["before"]] == [
        "s|shop:served"
    ]
    assert schema["after"][0]["reason"] == "needs a state the other step delivers"
    assert schema["delivers"] == ["shop:schema"] and schema["requires"] == ["shop:db_up"]
    served = items["s|shop:served"]
    assert [(u["id"], u["slot"]) for u in served["uses"]] == [("n|shop.cache", "client")]
    assert served["uses"][0]["expected"] == [] and served["probe"] == ""


def test_a_run_report_marks_each_state_ran_held_or_not_run():
    target = target_plan()
    plan = action_plan(target)
    report = RunReport(executed=("shop:db_up",), skipped=("shop:schema",), events=())
    page = render_target_html(target, plan, run_report=report)
    items = items_of(page)
    assert (items["s|shop:db_up"]["status"], items["s|shop:db_up"]["status_text"]) == ("ran", "ran")
    assert (items["s|shop:schema"]["status"], items["s|shop:schema"]["status_text"]) == (
        "held",
        "already held · skipped",
    )
    assert (items["s|shop:served"]["status"], items["s|shop:served"]["status_text"]) == ("pending", "not run")
    assert "1 ran" in page and "1 already held" in page
    assert 'class="status st-pending"' in page


def test_a_state_observed_at_plan_time_is_held_and_an_assumed_one_is_counted():
    target = target_plan()
    plan = action_plan(target, observed_states=frozenset({"lab:lit"}), assumed_states=frozenset({"shop:schema"}))
    page = render_target_html(target, plan)
    items = items_of(page)
    assert "s|lab:lit" not in items or items["s|lab:lit"]["status"] == "held"
    assert items["t|lab"]["held"] == ["lit"]
    assert items["t|shop"]["assumed"] == ["schema"]
    assert "1 assumed" in page


def test_a_target_card_lists_goals_aliases_and_counts():
    target = target_plan()
    items = items_of(render_target_html(target, action_plan(target)))
    shop = items["t|shop"]
    assert (shop["kind"], shop["goals"]) == ("target", ["served"])
    assert shop["aliases"] == [["shop.main", "shop.pool"]]
    assert shop["counts"] == [["capabilities", "3"], ["bring-up steps", "3"]]
    assert [t["id"] for t in shop["top_level"]] == ["n|shop.cache", "n|shop.ep"]


def test_config_schemas_and_issues_reach_the_capability_they_belong_to():
    target = target_plan()
    schema = {"acme.endpoint": [{"name": "port", "type": "int"}]}
    issues = (("shop.ep", "acme.endpoint", "port must be positive"), ("lab.gw", "acme.endpoint", "tls unknown"))
    items = items_of(render_target_html(target, action_plan(target), config_schemas=schema, config_issues=issues))
    assert items["n|shop.ep"]["config_issues"] == ["port must be positive"]
    assert items["n|lab.gw"]["config_issues"] == ["tls unknown"]
    assert items["n|shop.ep"]["config_schema"] == [{"name": "port", "type": "int"}]
    assert items["n|shop.pool"]["config_issues"] == [] and items["n|shop.pool"]["config_schema"] == []


def test_without_an_action_plan_each_scope_says_nothing_was_planned():
    target = target_plan()
    page = render_target_html(target, None)
    assert page.count("no bring-up steps were planned for this scope") == 2
    assert "0 bring-up steps" in page and "BRING-UP ORDER" in page
    assert cards_of(page, "state") == []


def test_a_failed_gate_one_banner_names_the_gate_and_each_scope_counts_its_errors():
    target = target_plan()
    from score.itf.core.octo import resolve_target as rt

    failed = rt(frozenset({NodeClaim(scope="shop", name="x", contract="db.pool")}))
    assert not failed.ok()
    failure = ResolutionFailed(1, "capabilities", failed.diagnostics, "boom")
    page = render_target_html(target, None, failure=failure)
    assert "Gate 1 · capabilities failed: nothing was brought up" in page
    assert page.count("no action plan: Gate 1 failed, see the error above") == 2
    assert "<pre>" in page


def gate_two_failure(goal_state="served"):
    target = target_plan()
    unsatisfied = StateContractClaim(
        token="served",
        impl="m:serve",
        scope="lab",
        uses=(Need("client", "cache.client", Shape.of("get")),),
    )
    top = StateContractClaim(token="top", impl="m:top", scope="lab", requires=frozenset({"served"}))
    goal = GoalClaim(scope="lab", states=frozenset({goal_state}))
    result = resolve_actions(frozenset({unsatisfied, top, goal}), target)
    assert not result.ok()
    return target, ResolutionFailed(2, "states", result.diagnostics, "boom"), (f"lab:{goal_state}",)


def test_a_scope_a_failed_gate_two_blocks_is_drawn_as_wanted_with_the_missing_capability_in_red():
    target, failure, goals = gate_two_failure()
    page = render_target_html(target, None, failure=failure, goals=goals)
    assert "WANTED · NOT PLANNED" in page
    assert "1 wanted states · 1 blocked · 1 missing capabilities" in page
    assert "Gate 2 · states failed" in page and "1 error(s)" in page
    assert cards_of(page, "node missing") == ["n|lab.client!missing"]
    assert "missing: cache.client" in page
    assert ("uses gap", "s|lab:served", "n|lab.client!missing") in re.findall(
        r'<g class="link ([^"]*)" data-a="([^"]*)" data-b="([^"]*)">', page
    )
    assert "tree root gap" in page
    # the shop scope had nothing wrong and nothing planned
    assert "no action plan: Gate 2 failed" in page
    items = items_of(page)
    served = items["s|lab:served"]
    assert (served["kind"], served["status"], served["status_text"]) == ("wanted", "blocked", "blocked")
    assert served["why"] == "a goal" and served["uses"] == [
        {"id": "n|lab.client!missing", "label": "cache.client", "slot": "client"}
    ]
    ghost = items["n|lab.client!missing"]
    assert (ghost["kind"], ghost["slot"], ghost["contract"], ghost["ref"]) == (
        "missing",
        "client",
        "cache.client",
        "lab.client (missing)",
    )
    assert ghost["blocks"] == [{"id": "s|lab:served", "label": "lab:served"}]
    assert ghost["fix"].startswith("share it into this scope") and ghost["why"] == "a goal"
    assert ghost["elsewhere"] == [{"id": "n|shop.cache", "label": "shop.cache"}]
    assert "n|shop.cache" in ghost["related"] and "n|lab.client!missing" in items["t|lab"]["related"]
    assert items["t|lab"]["goals"] == ["served"]


def test_a_blocked_state_a_goal_depends_on_says_which_goal_requires_it():
    target, failure, _ = gate_two_failure("top")
    items = items_of(render_target_html(target, None, failure=failure, goals=("lab:top",)))
    assert items["n|lab.client!missing"]["why"] == "required by lab:top (a goal)"
    assert items["s|lab:served"]["why"] == "required by lab:top (a goal)"
    assert items["s|lab:top"]["status"] == "pending"


def test_a_goal_the_failure_does_not_block_is_wanted_but_pending():
    target, failure, _ = gate_two_failure()
    page = render_target_html(target, None, failure=failure, goals=("lab:served", "lab:lit"))
    items = items_of(page)
    assert (items["s|lab:lit"]["status"], items["s|lab:lit"]["status_text"], items["s|lab:lit"]["why"]) == (
        "pending",
        "not planned",
        "a goal",
    )
    assert items["s|lab:lit"]["uses"] == []
    assert items["t|lab"]["goals"] == ["lit", "served"]
    assert 'class="item state pending"' in page and 'class="item state blocked"' in page
    assert "2 wanted states · 1 blocked" in page


def test_a_title_is_escaped_and_the_embedded_data_cannot_close_the_script():
    target = target_plan()
    page = render_target_html(target, action_plan(target), title="<b>x</b>")
    assert "<title>&lt;b&gt;x&lt;/b&gt;</title>" in page
    data = re.search(r'id="itf-data">(.*?)</script>', page, re.S).group(1)
    assert "<" not in data and ">" not in data
