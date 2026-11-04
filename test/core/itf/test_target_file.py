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
"""The target file format: entries, include, overrides, scopes, bind, goals, explicit-only parts."""

import textwrap

import kv_actions
import kv_parts
import pytest

from score.itf.core import TargetFileError, ConfigValidationFailed, ResolutionFailed, Session
from score.itf.core.frontends import target_file


def plan(tmp_path, text, *, overrides=(), **options):
    session = Session(
        [kv_parts],
        target=textwrap.dedent(text),
        overrides=overrides,
        plan_only=True,
        run_dir=tmp_path / "run",
        **options,
    )
    return session.resolve()


def nodes(session):
    return {n.ref.replace("__itf_root__.", ""): n for n in session.target_plan.nodes}


def steps(session):
    return [s.impl.rpartition(":")[2] for s in session.action_plan.steps]


def test_an_empty_target_file_is_valid(tmp_path):
    session = Session(target="{}", plan_only=True, run_dir=tmp_path / "run").resolve()
    assert session.target_plan.nodes == ()


def test_no_target_at_all_is_an_empty_target_file(tmp_path):
    session = Session(plan_only=True, run_dir=tmp_path / "run").resolve()
    assert session.target.names() == ()


def test_policies_are_explicit_ordered_and_can_clear_inheritance(tmp_path):
    assert target_file.load({})["policies"] == []
    base = tmp_path / "base.yaml"
    base.write_text("policies: [common.py, common.py]\n", encoding="utf-8")
    assert target_file.load({"include": [str(base)], "policies": ["device.py"]})["policies"] == [
        "common.py",
        "device.py",
    ]
    assert target_file.load({"include": [str(base)], "policies": []})["policies"] == []
    assert target_file.load_all({"include": [str(base)]}, [{"goals": []}])["policies"] == ["common.py"]
    assert target_file.load_all({"include": [str(base)]}, [{"policies": []}])["policies"] == []


@pytest.mark.parametrize("value", [None, "policy.py", [""], [1], {}])
def test_policies_must_be_a_list_of_paths(value):
    with pytest.raises(TargetFileError, match="policies is a list"):
        target_file.load({"policies": value})


def test_the_short_and_the_long_entry_are_the_same_role(tmp_path):
    short = plan(tmp_path, "capabilities:\n  store: local.store\n")
    long = plan(tmp_path, "capabilities:\n  store:\n    factory: local.store\n")
    assert nodes(short)["store"].provider == nodes(long)["store"].provider == "local.store"
    assert nodes(short)["store"].contract == "kv.store"


def test_the_role_is_the_name_and_the_factory_the_provider(tmp_path):
    session = plan(
        tmp_path,
        """
        capabilities:
          primary: local.store
          secondary: local.store
        """,
    )
    assert sorted(nodes(session)) == ["primary", "secondary"]


def test_with_is_the_settings_and_is_checked_against_the_schema(tmp_path):
    session = plan(tmp_path, "capabilities:\n  store:\n    factory: local.store\n    with:\n      name: x\n")
    assert dict(nodes(session)["store"].config) == {"name": "x"}
    with pytest.raises(ConfigValidationFailed, match=r"store \(local.store\).*size"):
        plan(tmp_path, "capabilities:\n  store:\n    factory: local.store\n    with:\n      size: big\n")
    with pytest.raises(ConfigValidationFailed, match="unknown key"):
        plan(tmp_path, "capabilities:\n  store:\n    factory: local.store\n    with:\n      nme: x\n")


def test_environment_references_in_with_are_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("KV_SIZE", "16")
    monkeypatch.delenv("KV_NAME", raising=False)
    session = plan(
        tmp_path,
        """
        capabilities:
          store:
            factory: local.store
            with:
              size: ${KV_SIZE}
              name: ${KV_NAME:-fallback}
        """,
    )
    assert dict(nodes(session)["store"].config) == {"name": "fallback", "size": 16}
    with pytest.raises(TargetFileError, match="KV_NAME"):
        plan(tmp_path, "capabilities:\n  store:\n    factory: local.store\n    with:\n      name: ${KV_NAME}\n")


def test_include_is_merged_first_and_this_file_wins(tmp_path):
    (tmp_path / "base.itf.yaml").write_text(
        "capabilities:\n  store:\n    factory: local.store\n    with:\n      name: base\n      size: 4\n"
        "  view: local.view\n",
        encoding="utf-8",
    )
    top = tmp_path / "top.itf.yaml"
    top.write_text(
        "include:\n  - base.itf.yaml\ncapabilities:\n  store:\n    with:\n      name: top\n", encoding="utf-8"
    )
    session = Session([kv_parts], target=str(top), plan_only=True, run_dir=tmp_path / "run").resolve()
    found = nodes(session)
    assert sorted(found) == ["store", "view"]
    assert dict(found["store"].config) == {"name": "top", "size": 4}


def test_an_include_cycle_is_an_error(tmp_path):
    (tmp_path / "a.yaml").write_text("include: b.yaml\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("include: a.yaml\n", encoding="utf-8")
    with pytest.raises(TargetFileError, match="cycle"):
        target_file.load(str(tmp_path / "a.yaml"))


def test_an_override_file_is_merged_by_role(tmp_path):
    target = "capabilities:\n  store:\n    factory: local.store\n    with:\n      name: lab1\n      size: 2\n"
    over = tmp_path / "lab2.itf.yaml"
    over.write_text("capabilities:\n  store:\n    with:\n      name: lab2\n", encoding="utf-8")
    session = plan(tmp_path, target, overrides=[str(over)])
    assert dict(nodes(session)["store"].config) == {"name": "lab2", "size": 2}


def test_a_second_instance_of_one_factory_is_overridden_by_its_own_role(tmp_path):
    target = "capabilities:\n  console: local.store\n  debug: local.store\n"
    over = "capabilities:\n  debug:\n    with:\n      name: second\n"
    session = plan(tmp_path, target, overrides=[over])
    assert dict(nodes(session)["debug"].config) == {"name": "second"}
    assert dict(nodes(session)["console"].config) == {}


def test_an_override_can_remove_a_role(tmp_path):
    target = "capabilities:\n  console: local.store\n  debug: local.store\n"
    session = plan(tmp_path, target, overrides=["capabilities:\n  debug:\n    remove: true\n"])
    assert set(nodes(session)) == {"console"}


def test_an_override_that_changes_the_factory_starts_its_settings_afresh(tmp_path):
    from score.itf.core.frontends import target_file

    target = "capabilities:\n  store:\n    factory: local.store\n    with:\n      name: a\n      size: 2\n"
    over = "capabilities:\n  store:\n    factory: local.other\n    with:\n      size: 3\n"
    assert target_file.load_all(target, [over])["capabilities"]["store"] == {
        "factory": "local.other",
        "with": {"size": 3},
    }


def test_remove_stands_alone(tmp_path):
    with pytest.raises(TargetFileError, match="stands alone"):
        plan(tmp_path, "capabilities:\n  debug:\n    factory: local.store\n    remove: true\n")


def test_an_override_for_a_role_without_a_factory_is_an_error(tmp_path):
    with pytest.raises(TargetFileError, match="role 'ghost': no factory"):
        plan(
            tmp_path,
            "capabilities:\n  store: local.store\n",
            overrides=["capabilities:\n  ghost:\n    with:\n      a: 1\n"],
        )


def test_overrides_need_a_target_file():
    with pytest.raises(ValueError, match="need a target file"):
        Session(overrides=["{}"])


def test_unknown_keys_are_errors_that_name_the_valid_ones(tmp_path):
    with pytest.raises(TargetFileError, match="unknown key.*parts.*capabilities"):
        plan(tmp_path, "parts:\n  store: local.store\n")
    with pytest.raises(TargetFileError, match="role 'store' has unknown key.*part"):
        plan(tmp_path, "capabilities:\n  store:\n    part: local.store\n")
    with pytest.raises(TargetFileError, match="scope 'gw' has unknown key"):
        plan(tmp_path, "scopes:\n  gw:\n    nodes: {}\n")


def test_an_unknown_factory_names_what_its_pack_has(tmp_path):
    with pytest.raises(TargetFileError, match=r"'local.nope' is not a known capability factory.*local.store"):
        plan(tmp_path, "capabilities:\n  store: local.nope\n")


def test_a_label_without_a_pack_says_how_to_write_it(tmp_path):
    with pytest.raises(TargetFileError, match="<pack>.<name>"):
        plan(tmp_path, "capabilities:\n  store: store\n")


def test_a_role_must_be_an_identifier(tmp_path):
    with pytest.raises(TargetFileError, match="Python identifier"):
        plan(tmp_path, "capabilities:\n  my-store: local.store\n")


def test_nothing_enters_a_target_unless_it_is_listed(tmp_path):
    session = plan(tmp_path, "capabilities:\n  store: local.store\n")
    assert sorted(nodes(session)) == ["store"]  # the view exists in the catalog; it is not in the target


def test_a_missing_provider_is_an_error_naming_the_candidates(tmp_path):
    with pytest.raises(ResolutionFailed) as error:
        plan(tmp_path, "capabilities:\n  view: local.view\n")
    text = str(error.value)
    assert "view (local.view) needs a 'kv.store' for its slot 'store'" in text
    assert "Candidates: local.store" in text
    assert "store: local.store" in text  # the fix


def test_a_slot_with_two_candidates_is_ambiguous_until_bound(tmp_path):
    both = "capabilities:\n  first: local.store\n  second: local.store\n  view: local.view\n"
    with pytest.raises(ResolutionFailed, match="more than one role could fill slot 'store'.*first, second"):
        plan(tmp_path, both)
    session = plan(
        tmp_path,
        both.replace("view: local.view", "view:\n    factory: local.view\n    bind:\n      store: second\n"),
    )
    assert dict(nodes(session)["view"].bindings)["store"].endswith(".second")


def test_a_bind_names_a_slot_the_factory_has(tmp_path):
    with pytest.raises(TargetFileError, match="no slot 'nothing'.*its slots are: store"):
        plan(
            tmp_path,
            "capabilities:\n  store: local.store\n  view:\n    factory: local.view\n    bind:\n      nothing: store\n",
        )


def test_a_goal_is_explicit_and_its_action_comes_with_the_listed_packs(tmp_path):
    kv_parts.EVENTS.clear()
    session = plan(
        tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - state: kv.seeded\n    by: local.seed_a\n"
    )
    assert steps(session) == ["seed_a"]


def test_no_goal_no_steps(tmp_path):
    session = plan(tmp_path, "capabilities:\n  store: local.store\n")
    assert steps(session) == []


def test_two_possible_actions_without_by_is_a_compile_error_naming_both(tmp_path):
    with pytest.raises(TargetFileError) as error:
        plan(tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - kv.seeded\n")
    text = str(error.value)
    assert "'kv.seeded'" in text and "local.seed_a" in text and "local.seed_b" in text and "by:" in text


def test_by_chooses_and_a_state_reached_through_after_needs_its_own_by(tmp_path):
    base = "capabilities:\n  store: local.store\ngoals:\n  - kv.ready\n"
    with pytest.raises(TargetFileError, match="kv.seeded"):
        plan(tmp_path, base)  # kv.ready needs kv.seeded, which two actions could make
    session = plan(tmp_path, base + "  - state: kv.seeded\n    by: local.seed_b\n")
    assert steps(session) == ["seed_b", "ready"]


def test_by_must_name_an_action_that_makes_the_state(tmp_path):
    with pytest.raises(TargetFileError, match="does not make it true"):
        plan(tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - state: kv.ready\n    by: local.seed_a\n")
    with pytest.raises(TargetFileError, match="not a known action"):
        plan(tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - state: kv.ready\n    by: local.nope\n")


def test_a_goal_nothing_makes_true_is_diagnosed(tmp_path):
    with pytest.raises(ResolutionFailed, match="cannot be reached"):
        plan(tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - kv.unknown\n")


def test_assume_stands_in_for_the_action(tmp_path):
    text = """
        capabilities:
          store: local.store
        goals:
          - kv.ready
        assume:
          - state: kv.seeded
            owner: lab
            reason: seeded by the rack
    """
    session = plan(tmp_path, text)
    assert steps(session) == ["ready"]
    assert session._assumed


def test_scopes_have_their_own_roles_and_share_a_root_role(tmp_path):
    session = plan(
        tmp_path,
        """
        capabilities:
          store: local.store
        scopes:
          gw:
            capabilities:
              view: local.view
            share:
              - store
        """,
    )
    assert session.target.scopes() == ("gw",)
    assert session.target.gw.names() == ("store", "view")
    assert session.target_plan.resolve("gw.store") == "__itf_root__.store"
    assert session.target.names() == ("store",)  # nothing leaks back to the root


def test_a_scope_does_not_fall_back_to_the_root(tmp_path):
    with pytest.raises(ResolutionFailed, match="view.*needs a 'kv.store'"):
        plan(
            tmp_path,
            "capabilities:\n  store: local.store\nscopes:\n  gw:\n    capabilities:\n      view: local.view\n",
        )


def test_share_names_a_root_role(tmp_path):
    with pytest.raises(TargetFileError, match="share names 'ghost'"):
        plan(tmp_path, "capabilities:\n  store: local.store\nscopes:\n  gw:\n    share:\n      - ghost\n")


def test_a_scope_name_is_checked(tmp_path):
    with pytest.raises(Exception, match="scope name"):
        plan(tmp_path, "scopes:\n  target:\n    capabilities: {}\n")


def test_a_goal_in_a_scope_with_its_own_by(tmp_path):
    session = plan(
        tmp_path,
        """
        capabilities:
          store: local.store
        scopes:
          gw:
            capabilities:
              store: local.store
            goals:
              - state: kv.seeded
                by: local.seed_b
        """,
    )
    assert steps(session) == ["seed_b"]
    assert session.action_plan.steps[0].delivers == ("gw:kv.seeded",)


RELATED = "capabilities:\n  store: local.store\ngoals:\n  - kv.ready\n  - state: kv.seeded\n    by: local.seed_b\n"


def test_a_relation_orders_two_states_the_actions_do_not_order(tmp_path):
    goals = "capabilities:\n  store: local.store\ngoals:\n  - kv.audited\n  - kv.ready\n"
    goals += "  - state: kv.seeded\n    by: local.seed_b\n"
    session = plan(tmp_path, goals + "relations:\n  - state: kv.audited\n    after:\n      - kv.ready\n")
    assert steps(session) == ["seed_b", "ready", "audit"]
    session = plan(tmp_path, goals + "relations:\n  - state: kv.ready\n    after:\n      - kv.audited\n")
    order = steps(session)
    assert order.index("audit") < order.index("ready")


def test_a_relation_that_contradicts_the_actions_is_a_resolution_failure(tmp_path):
    with pytest.raises(ResolutionFailed):
        plan(tmp_path, RELATED + "relations:\n  - state: kv.seeded\n    after:\n      - kv.ready\n")


def test_a_relation_that_breaks_a_state_is_added(tmp_path):
    session = plan(
        tmp_path, RELATED + "  - kv.audited\nrelations:\n  - state: kv.audited\n    breaks:\n      - kv.seeded\n"
    )
    by_state = {s.delivers: s for s in session.action_plan.steps}
    assert by_state[("__itf_root__:kv.audited",)].invalidates == ("__itf_root__:kv.seeded",)


def test_a_relation_naming_a_state_no_listed_action_makes_is_a_compile_error(tmp_path):
    with pytest.raises(TargetFileError, match="no listed action makes 'kv.ghost' true and it is not assumed"):
        plan(tmp_path, RELATED + "relations:\n  - state: kv.ghost\n    after:\n      - kv.seeded\n")
    with pytest.raises(TargetFileError, match="no listed action makes 'kv.ghost'"):
        plan(tmp_path, RELATED + "relations:\n  - state: kv.ready\n    breaks:\n      - kv.ghost\n")


def test_a_relation_may_name_an_assumed_state_in_after(tmp_path):
    text = (
        "capabilities:\n  store: local.store\ngoals:\n  - kv.ready\nassume:\n  - kv.seeded\n"
        "relations:\n  - state: kv.ready\n    after:\n      - kv.seeded\n"
    )
    assert steps(plan(tmp_path, text)) == ["ready"]


def test_a_relation_on_an_ambiguous_state_needs_by(tmp_path):
    text = "capabilities:\n  store: local.store\nrelations:\n  - state: kv.seeded\n    after:\n      - kv.ready\n"
    with pytest.raises(TargetFileError, match="can be made true by local.seed_a or local.seed_b"):
        plan(tmp_path, text)


def test_a_relation_has_state_and_lists(tmp_path):
    with pytest.raises(TargetFileError, match="neither `after` nor `breaks`"):
        plan(tmp_path, "relations:\n  - state: kv.ready\n")
    with pytest.raises(TargetFileError, match="after is a list"):
        plan(tmp_path, "relations:\n  - state: kv.ready\n    after: kv.seeded\n")
    with pytest.raises(TargetFileError, match="a relation is `state:`"):
        plan(tmp_path, "relations:\n  - state: kv.ready\n    before: kv.seeded\n")


def test_relations_merge_by_state_across_includes_and_overrides(tmp_path):
    (tmp_path / "base.itf.yaml").write_text(
        RELATED + "relations:\n  - state: kv.ready\n    breaks:\n      - kv.seeded\n", encoding="utf-8"
    )
    over = "relations:\n  - state: kv.ready\n    after:\n      - kv.seeded\n"
    merged = target_file.load_all(str(tmp_path / "base.itf.yaml"), [over])
    assert merged["relations"] == [{"state": "kv.ready", "after": ["kv.seeded"], "breaks": ["kv.seeded"]}]


def test_a_relation_in_a_scope_is_for_that_scope(tmp_path):
    session = plan(
        tmp_path,
        """
        capabilities:
          store: local.store
        scopes:
          gw:
            capabilities:
              store: local.store
            goals:
              - kv.audited
              - kv.ready
              - state: kv.seeded
                by: local.seed_b
            relations:
              - state: kv.audited
                after:
                  - kv.ready
        """,
    )
    assert steps(session) == ["seed_b", "ready", "audit"]
    audit = session.action_plan.steps[-1]
    assert audit.delivers == ("gw:kv.audited",) and audit.requires == ("gw:kv.ready",)


def test_a_factory_says_whether_a_later_process_observes_what_it_created(tmp_path):
    session = plan(tmp_path, "capabilities:\n  store: local.store\n")
    factories = session.catalog.factories
    assert (factories["local.cache"].has_teardown, factories["local.cache"].observable({})) == (True, True)
    assert factories["local.memo"].observable({}) is False and factories["local.memo"].observable({"dir": "x"})
    assert (factories["local.plain"].has_teardown, factories["local.plain"].observable({})) == (False, False)
    assert factories["local.store"].has_teardown and not factories["local.store"].observable({})


# ---- how an action's slots are filled: `actions:`, the sole candidate of the contract, else an error ----------

TWO_STORES = "capabilities:\n  store: local.store\n  other: local.store\n"


def action_plan(tmp_path, text):
    return plan(tmp_path, text).action_plan.steps[0]


def test_an_action_slot_is_not_filled_by_a_role_that_happens_to_carry_its_name(tmp_path):
    with pytest.raises(ResolutionFailed, match="more than one role could fill the action's slot.*other.*store"):
        plan(tmp_path, TWO_STORES + "goals:\n  - state: kv.seeded\n    by: local.seed_a\n")


def test_actions_bind_names_the_role_that_fills_an_action_slot(tmp_path):
    text = TWO_STORES + "goals:\n  - state: kv.seeded\n    by: local.seed_a\n"
    text += "actions:\n  local.seed_a:\n    bind:\n      store: other\n"
    assert dict(action_plan(tmp_path, text).uses)["store"].endswith(".other")


def test_actions_of_a_scope_bind_in_that_scope_only(tmp_path):
    text = """
        capabilities:
          store: local.store
        scopes:
          gw:
            capabilities:
              first: local.store
              second: local.store
            goals:
              - state: kv.seeded
                by: local.seed_a
            actions:
              local.seed_a:
                bind:
                  store: second
    """
    assert dict(action_plan(tmp_path, text).uses)["store"] == "gw.second"


def test_actions_bind_is_validated_like_a_role_entry(tmp_path):
    with pytest.raises(TargetFileError, match="'local.nope' is not a known action; pack local has: .*seed_a"):
        plan(tmp_path, TWO_STORES + "actions:\n  local.nope:\n    bind:\n      store: other\n")
    with pytest.raises(TargetFileError, match="local.seed_a has no slot 'nothing'; its slots are: store"):
        plan(tmp_path, TWO_STORES + "actions:\n  local.seed_a:\n    bind:\n      nothing: other\n")
    with pytest.raises(TargetFileError, match="role 'nope'.*roles: other, store"):
        plan(tmp_path, TWO_STORES + "actions:\n  local.seed_a:\n    bind:\n      store: nope\n")
    with pytest.raises(TargetFileError, match="unknown key"):
        plan(tmp_path, TWO_STORES + "actions:\n  local.seed_a:\n    with:\n      x: 1\n")


def test_actions_merge_by_label_across_includes_and_overrides(tmp_path):
    base = TWO_STORES + "goals:\n  - state: kv.seeded\n    by: local.seed_a\n"
    (tmp_path / "base.itf.yaml").write_text(base, encoding="utf-8")
    over = "actions:\n  local.seed_a:\n    bind:\n      store: other\n"
    session = Session(
        [kv_parts],
        target=str(tmp_path / "base.itf.yaml"),
        overrides=[over],
        plan_only=True,
        run_dir=tmp_path / "run",
    ).resolve()
    assert dict(session.action_plan.steps[0].uses)["store"].endswith(".other")


def test_an_action_with_a_slot_nothing_fills_is_not_a_candidate(tmp_path):
    session = Session(
        [kv_parts, kv_actions],
        target="capabilities:\n  store: local.store\ngoals:\n  - kv.indexed\n",
        plan_only=True,
        run_dir=tmp_path / "run",
    ).resolve()
    assert [s.impl.rpartition(":")[2] for s in session.action_plan.steps] == ["index_plain"]


def test_an_action_whose_slots_can_all_be_filled_stays_a_candidate_and_ambiguity_is_an_error(tmp_path):
    with pytest.raises(TargetFileError, match="can be made true by local.index_plain or local.index_with_lookup"):
        Session(
            [kv_parts, kv_actions],
            target="capabilities:\n  store: local.store\n  index: local.index\ngoals:\n  - kv.indexed\n",
            plan_only=True,
            run_dir=tmp_path / "run",
        ).resolve()
    session = Session(
        [kv_parts, kv_actions],
        target="capabilities:\n  store: local.store\n  index: local.index\ngoals:\n"
        "  - state: kv.indexed\n    by: local.index_with_lookup\n",
        plan_only=True,
        run_dir=tmp_path / "run",
    ).resolve()
    assert [s.impl.rpartition(":")[2] for s in session.action_plan.steps] == ["index_with_lookup"]


def test_an_action_slot_an_actions_bind_fills_counts_as_fillable(tmp_path):
    text = (
        "capabilities:\n  store: local.store\n  first: local.index\n  second: local.index\ngoals:\n  - kv.indexed\n"
        "actions:\n  local.index_with_lookup:\n    bind:\n      index: second\n"
    )
    with pytest.raises(TargetFileError, match="can be made true by local.index_plain or local.index_with_lookup"):
        Session([kv_parts, kv_actions], target=text, plan_only=True, run_dir=tmp_path / "run").resolve()
    # without the bind, two indexes leave index_with_lookup unfillable: only index_plain remains
    plain = text.split("actions:")[0]
    session = Session([kv_parts, kv_actions], target=plain, plan_only=True, run_dir=tmp_path / "run").resolve()
    assert [s.impl.rpartition(":")[2] for s in session.action_plan.steps] == ["index_plain"]


def test_a_target_file_cannot_locate_a_pack_named_local(tmp_path):
    text = "packs:\n  local: acme.plugin\ncapabilities:\n  store: local.store\n"
    with pytest.raises(TargetFileError, match="reserved for the project's policy"):
        Session([kv_parts], target=text, plan_only=True, run_dir=tmp_path / "run").resolve()


# ${NAME} values a project keeps out of its target file: the environment, else a .env file beside the target file.
ENV_TARGET = (
    "capabilities:\n  store:\n    factory: local.store\n    with:\n      name: ${KV_NAME}\n      size: ${KV_SIZE:-1}\n"
)


def plan_file(tmp_path, env_text: str | None):
    (tmp_path / "target.itf.yaml").write_text(ENV_TARGET)
    if env_text is not None:
        (tmp_path / ".env").write_text(env_text)
    session = Session([kv_parts], target=str(tmp_path / "target.itf.yaml"), plan_only=True, run_dir=tmp_path / "run")
    return dict(nodes(session.resolve())["store"].config)


def test_a_dotenv_file_beside_the_target_file_supplies_values(tmp_path, monkeypatch):
    monkeypatch.delenv("KV_NAME", raising=False)
    monkeypatch.delenv("KV_SIZE", raising=False)
    text = "# the lab's values\n\nexport KV_NAME='lab one'\nKV_SIZE=\"8\"\n"
    assert plan_file(tmp_path, text) == {"name": "lab one", "size": 8}


def test_the_environment_wins_over_the_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.setenv("KV_NAME", "from the environment")
    monkeypatch.delenv("KV_SIZE", raising=False)
    assert plan_file(tmp_path, "KV_NAME=from the file\n")["name"] == "from the environment"


def test_a_value_set_nowhere_names_the_dotenv_file_it_looked_in(tmp_path, monkeypatch):
    monkeypatch.delenv("KV_NAME", raising=False)
    with pytest.raises(TargetFileError, match=r"KV_NAME.*not set.*\.env"):
        plan_file(tmp_path, None)


def test_a_plan_only_session_can_plan_with_placeholders_for_unset_values(tmp_path, monkeypatch):
    monkeypatch.delenv("KV_NAME", raising=False)
    monkeypatch.delenv("KV_SIZE_UNSET", raising=False)
    text = "capabilities:\n  store:\n    factory: local.store\n    with:\n      name: ${KV_NAME}\n      size: ${KV_SIZE_UNSET}\n"
    session = Session([kv_parts], target=text, plan_only=True, unset="placeholder", run_dir=tmp_path / "run")
    config = dict(nodes(session.resolve())["store"].config)
    assert config == {"name": "${KV_NAME}", "size": "${KV_SIZE_UNSET}"}  # an int field accepts the placeholder too


def test_placeholders_are_for_planning_only():
    with pytest.raises(ValueError, match="plan_only"):
        Session(target="capabilities: {}\n", unset="placeholder")
