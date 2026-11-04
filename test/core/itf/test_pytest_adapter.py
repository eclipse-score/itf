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
"""The pytest adapter: `--itf-target`, ini, environment, overrides, gating, the `target` fixture, errors before any test."""

from types import ModuleType

import kv_parts
import pytest
import recording_parts

from score.itf import hookimpl
from score.itf.core.adapters.pytest.plugin import contributors_from_pytest

POLICY = 'pytest_plugins = ["kv_parts"]\n'
TARGET = "capabilities:\n  store: local.store\n  view: local.view\ngoals:\n  - state: kv.seeded\n    by: local.seed_a\n"
TEST = """
import score.itf as itf

def test_roles(target):
    assert target.view.read("seeded") == "a"

@itf.requires("command")
def test_needs_a_command(target):
    raise AssertionError("must have been deselected")

@itf.requires("store", contract="kv.store")
def test_needs_the_store(target):
    assert target.store.name
"""


@pytest.fixture(autouse=True)
def reset():
    kv_parts.EVENTS.clear()


def test_pytest_contributors_keep_explicit_pack_hooks_without_loading_a_policy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "policy.py").write_text("raise AssertionError('undeclared policy imported')\n")
    directory = tmp_path / "pack"
    directory.mkdir()
    (directory / "pack.yaml").write_text("name: explicit\nversion: 0.1.0\n")
    module = ModuleType("explicit_pack")
    module.__file__ = str(directory / "plugin.py")

    @hookimpl
    def itf_verify(session):
        session.check("explicit.pack", True)

    module.itf_verify = itf_verify
    manager = pytest.PytestPluginManager()
    manager.register(module)
    assert contributors_from_pytest(manager) == [(module, "plugin")]


def project(pytester, target=TARGET, ini=""):
    pytester.makepyfile(policy=POLICY)
    pytester.makepyfile(test_it=TEST)
    pytester.makefile(".yaml", target="policies: [policy.py]\n" + target)
    if ini:
        pytester.makefile(".ini", pytest=ini)


def test_a_target_file_given_on_the_command_line_builds_the_target(pytester):
    project(pytester)
    result = pytester.runpytest("--itf-target=target.yaml")
    result.assert_outcomes(passed=2, deselected=1)
    assert kv_parts.EVENTS[-1] == "store closed"


def test_the_ini_option_configures_the_target_file(pytester):
    project(pytester, ini="[pytest]\nitf_target = target.yaml\n")
    pytester.runpytest().assert_outcomes(passed=2, deselected=1)


def test_the_environment_configures_the_target_file(pytester, monkeypatch):
    project(pytester)
    monkeypatch.setenv("ITF_TARGET", "target.yaml")
    pytester.runpytest().assert_outcomes(passed=2, deselected=1)


@pytest.mark.parametrize("flags", [(), ("--itf-strict-gating",)])
def test_declared_policy_expectations_reject_before_collection_or_construction(pytester, flags):
    project(pytester)
    pytester.makepyfile(
        policy=POLICY
        + (
            "from typing import Protocol\nclass Reader(Protocol):\n"
            "    __contract__ = 'kv.view'\n"
            "    def read(self, key: str, *, unsupported_keyword: bool = False) -> str: ...\n"
            "itf_expect = [Reader]\n"
        )
    )
    result = pytester.runpytest("--itf-target=target.yaml", *flags)
    assert result.ret != 0
    output = result.stdout.str() + result.stderr.str()
    assert "policy expectations" in output and "read" in output
    assert kv_parts.EVENTS == []


def test_protocol_call_requirements_deselect_before_target_construction(pytester):
    project(pytester)
    pytester.makepyfile(
        test_it="""
        from typing import Protocol
        import score.itf as itf

        class Reader(Protocol):
            __contract__ = "kv.view"

            def read(self, key: str, *, unsupported_keyword: bool = False) -> str: ...

        @itf.requires("view", shape=Reader)
        def test_requires_an_unsupported_call(target):
            raise AssertionError("must be deselected before the target exists")
    """
    )
    result = pytester.runpytest("--itf-target=target.yaml")
    result.assert_outcomes(deselected=1)
    assert kv_parts.EVENTS == []


def test_an_override_file_changes_one_role(pytester):
    project(pytester)
    pytester.makefile(".yaml", lab="capabilities:\n  store:\n    with:\n      name: lab\n")
    pytester.makepyfile(test_it="def test_named(target):\n    assert target.store.name == 'lab'\n")
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-override=lab.yaml")
    result.assert_outcomes(passed=1)


def test_overrides_come_from_the_environment_too(pytester, monkeypatch):
    project(pytester)
    pytester.makefile(".yaml", lab="capabilities:\n  store:\n    with:\n      name: lab\n")
    pytester.makepyfile(test_it="def test_named(target):\n    assert target.store.name == 'lab'\n")
    monkeypatch.setenv("ITF_OVERRIDE", "lab.yaml")
    pytester.runpytest("--itf-target=target.yaml").assert_outcomes(passed=1)


def test_plan_prints_the_target_file_the_plan_and_the_gating_and_runs_nothing(pytester):
    project(pytester)
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-plan")
    out = result.stdout.str()
    assert "Target file:" in out and "store (local.store)" in out and "kv.seeded" in out
    assert "deselected: target has no role 'command'" in out
    assert kv_parts.EVENTS == []


def test_a_target_file_that_does_not_compile_stops_before_any_test(pytester):
    project(pytester, target="capabilities:\n  view: local.view\n")
    result = pytester.runpytest("--itf-target=target.yaml")
    assert result.ret != 0
    out = result.stdout.str() + result.stderr.str()
    assert "plan failed at gate 1" in out and "Candidates: local.store" in out


def test_a_target_file_error_is_reported_as_rejected(pytester):
    project(pytester, target="parts:\n  store: local.store\n")
    result = pytester.runpytest("--itf-target=target.yaml")
    assert "target file rejected" in result.stdout.str() + result.stderr.str()


def test_an_unusable_target_file_value_is_a_usage_error(pytester):
    project(pytester)
    result = pytester.runpytest("--itf-target=missing.yaml")
    assert result.ret == 4
    assert "no usable target file" in result.stdout.str() + result.stderr.str()


def test_overrides_without_a_target_file_are_a_usage_error(pytester):
    pytester.makefile(".yaml", lab="capabilities: {}\n")
    pytester.makepyfile(test_it="def test_x(): pass\n")
    result = pytester.runpytest("--itf-override=lab.yaml")
    assert result.ret == 4


def test_without_any_target_file_the_target_fixture_says_so(pytester):
    pytester.makepyfile(test_it="def test_x(target): pass\n")
    result = pytester.runpytest()
    result.assert_outcomes(errors=1)
    assert "no target file" in result.stdout.str()


def test_strict_gating_deselects_missing_optional_roles(pytester):
    project(pytester)
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-strict-gating")
    result.assert_outcomes(passed=2, deselected=1)


def test_strict_preflight_rejects_api_drift_before_any_target_is_constructed(pytester):
    project(pytester)
    pytester.makepyfile(
        test_it="""
        import score.itf as itf

        @itf.requires("view", contract="kv.view", shape=["read"])
        def test_basic(target):
            raise AssertionError("must not execute when strict preflight fails")

        @itf.requires("view", contract="kv.view", shape=["unsupported"])
        def test_extended(target):
            raise AssertionError("must not execute")
    """
    )
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-strict-gating")
    assert result.ret == 4
    output = result.stdout.str() + result.stderr.str()
    assert "ITF compatibility preflight" in output
    assert "target.view / kv.view: partial" in output
    assert "unsupported" in output and "test_extended" in output
    assert kv_parts.EVENTS == []


def test_loose_preflight_runs_compatible_tests_and_records_api_deviations(pytester):
    import json

    project(pytester)
    pytester.makepyfile(
        test_it="""
        import score.itf as itf

        @itf.requires("view", contract="kv.view", shape=["read"])
        def test_basic(target):
            assert target.view.read("seeded") == "a"

        @itf.requires("view", contract="kv.view", shape=["unsupported"])
        def test_extended(target):
            raise AssertionError("must be deselected")
    """
    )
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-artifacts=full")
    result.assert_outcomes(passed=1, deselected=1)
    report = json.loads((pytester.path / "itf-run" / "preflight.json").read_text())
    (group,) = report["groups"]
    assert group["status"] == "partial"
    (blocked,) = [profile for profile in group["profiles"] if profile["status"] == "incompatible"]
    assert blocked["provider"] == "local.view"
    assert blocked["diagnostics"][0]["code"] == "SHAPE_MISSING_MEMBER"
    assert blocked["tests"] == ["test_it.py::test_extended"]
    assert blocked["given"]["members"]


@pytest.mark.parametrize("strict", [False, True])
def test_a_required_undeclared_major_never_runs_the_test(pytester, strict):
    project(pytester)
    pytester.makepyfile(
        test_it="""
        import score.itf as itf

        @itf.requires("view", contract="kv.view@3")
        def test_versioned(target):
            raise AssertionError("provider major is unknown")
    """
    )
    result = pytester.runpytest("--itf-target=target.yaml", *(["--itf-strict-gating"] if strict else []))
    if strict:
        assert result.ret == 4
        assert "declares no contract major" in result.stderr.str()
    else:
        result.assert_outcomes(deselected=1)
    assert kv_parts.EVENTS == []


@pytest.mark.parametrize("option", ["--collect-only", "--itf-plan"])
def test_collecting_and_planning_touch_nothing(pytester, option):
    recording_parts.CALLS.clear()
    recording_parts.HOLDS[:] = [True]
    pytester.makepyfile(policy='pytest_plugins = ["recording_parts"]\n')
    pytester.makepyfile(test_it="def test_x(target):\n    pass\n")
    pytester.makefile(
        ".yaml", target="policies: [policy.py]\ncapabilities:\n  thing: local.thing\ngoals:\n  - rec.ready\n"
    )
    pytester.runpytest("--itf-target=target.yaml", option)
    assert recording_parts.CALLS == []


def test_the_old_option_names_are_gone(pytester):
    project(pytester)
    for option in ("--itf-composition=target.yaml", "--itf-strict-shapes"):
        result = pytester.runpytest(option)
        assert result.ret == 4 and "unrecognized arguments" in result.stderr.str()


def test_an_unspecified_ini_still_finds_the_pyproject_option(pytester):
    project(pytester)
    pytester.makepyprojecttoml('[tool.pytest.ini_options]\nitf_target = "target.yaml"\n')
    pytester.runpytest().assert_outcomes(passed=2, deselected=1)


# The project's own ITF code is declared in the target file. Conftests are pytest's alone.
TARGET_POLICY = """
from score.itf.core import capability


class Store:
    def get(self):
        return "a"


@capability("acme/store")
def store() -> Store:
    return Store()
"""
SUITE_CONFTEST = "import pytest\n\n\n@pytest.fixture\ndef {name}():\n    return '{name}'\n"


def suite_project(pytester):
    """target/ holds the target file and its policy; the suite's tests and conftests live elsewhere."""
    pytester.makeconftest(SUITE_CONFTEST.format(name="above"))
    (pytester.mkdir("target") / "policy.py").write_text(TARGET_POLICY)
    (pytester.path / "target" / "target.yaml").write_text(
        "policies: [target/policy.py]\ncapabilities:\n  store: local.store\n"
    )
    deep = pytester.mkdir("suite") / "deep"
    deep.mkdir()
    (deep / "conftest.py").write_text(SUITE_CONFTEST.format(name="deep"))
    (deep / "test_it.py").write_text(
        "def test_store(target, above, deep):\n    assert (target.store.get(), above, deep) == ('a', 'above', 'deep')\n"
    )


def test_the_declared_policy_is_loaded_wherever_the_tests_and_their_conftests_are(pytester):
    suite_project(pytester)
    pytester.runpytest("--itf-target=target/target.yaml", "suite").assert_outcomes(passed=1)


def test_the_policy_is_loaded_once_when_its_directory_is_collected_too(pytester):
    suite_project(pytester)
    pytester.runpytest("--itf-target=target/target.yaml", "target", "suite").assert_outcomes(passed=1)


def test_undeclared_policies_beside_the_target_and_in_the_cwd_are_ignored(pytester):
    pytester.makepyfile(policy="raise AssertionError('CWD policy imported')")
    targets = pytester.mkdir("targets")
    (targets / "policy.py").write_text("raise AssertionError('target policy imported')\n")
    (targets / "target.yaml").write_text("capabilities: {}\n")
    pytester.makepyfile(test_it="def test_empty(target):\n    assert target is not None\n")
    pytester.runpytest("--itf-target=targets/target.yaml").assert_outcomes(passed=1)


def test_a_missing_declared_policy_is_a_clear_usage_error(pytester):
    pytester.makefile(".yaml", target="policies: [missing.py]\ncapabilities: {}\n")
    pytester.makepyfile(test_it="def test_never_runs(target):\n    raise AssertionError\n")
    result = pytester.runpytest("--itf-target=target.yaml")
    assert result.ret == 4
    output = result.stdout.str() + result.stderr.str()
    assert "policy" in output and "missing.py" in output and "is not a file" in output
    assert kv_parts.EVENTS == []


@pytest.mark.parametrize(
    "invalid", [None, "first", "second"], ids=["composed", "first-expectation", "second-expectation"]
)
def test_multiple_explicit_modules_contribute_parts_hooks_and_expectations(pytester, invalid):
    reader_call = (
        "def read(self, key: str, *, unsupported: bool = False) -> str: ..."
        if invalid == "first"
        else "def read(self, key: str) -> str: ..."
    )
    lamp_call = "def unsupported(self): ..." if invalid == "second" else "def get(self): ..."
    pytester.makepyfile(
        first=POLICY + "from typing import Protocol\nfrom score.itf import hookimpl\n"
        "class Reader(Protocol):\n    __contract__ = 'kv.view'\n"
        f"    {reader_call}\n"
        "itf_expect = [Reader]\n"
        "@hookimpl\ndef itf_verify(session):\n"
        "    with open('policy_calls', 'a') as output:\n        output.write('first\\n')\n",
        second=TARGET_POLICY.replace("def store", "def lamp")
        + "\nfrom typing import Protocol\nfrom score.itf import hookimpl\n"
        "class Lamp(Protocol):\n    __contract__ = 'acme/store'\n"
        f"    {lamp_call}\n"
        "itf_expect = [Lamp]\n"
        "@hookimpl\ndef itf_verify(session):\n"
        "    with open('policy_calls', 'a') as output:\n        output.write('second\\n')\n",
        test_it="def test_parts(target):\n    assert target.view.read('seeded') == 'a'\n    assert target.lamp.get() == 'a'\n",
    )
    pytester.makefile(
        ".yaml",
        target="policies: [first.py, second.py]\n"
        + TARGET.replace("  view: local.view", "  view: local.view\n  lamp: local.lamp"),
    )
    result = pytester.runpytest("--itf-target=target.yaml")
    if invalid is None:
        result.assert_outcomes(passed=1)
        assert sorted((pytester.path / "policy_calls").read_text().splitlines()) == ["first", "second"]
        assert kv_parts.EVENTS[-1] == "store closed"
    else:
        assert result.ret == 4
        output = result.stdout.str() + result.stderr.str()
        assert "policy expectations" in output and "unsupported" in output
        assert kv_parts.EVENTS == []


@pytest.mark.parametrize(
    "code",
    [
        TARGET_POLICY.replace("def store", "def other_store"),
        "from score.itf.core import hookimpl\n\n\n@hookimpl\ndef itf_verify(session):\n    pass\n",
    ],
    ids=["a part", "an ITF hook"],
)
def test_itf_code_in_a_conftest_is_an_error_that_points_to_the_policy(pytester, code):
    suite_project(pytester)
    (pytester.path / "suite" / "conftest.py").write_text(code)
    result = pytester.runpytest("--itf-target=target/target.yaml", "suite")
    assert result.ret == 4
    err = result.stderr.str()
    assert "suite/conftest.py" in err and "list their policy file in the target's policies" in err


# What a run leaves in itf-run/: nothing, what a person reads, or every file ITF writes.
def run_files(pytester) -> set:
    run = pytester.path / "itf-run"
    return {p.name for p in run.iterdir()} if run.exists() else set()


def test_by_default_a_run_leaves_the_plan_report_and_evidence_but_no_duplicate_log(pytester):
    project(pytester)
    result = pytester.runpytest("--itf-target=target.yaml")
    result.assert_outcomes(passed=2, deselected=1)
    assert "ITF session" in result.stdout.str()
    assert run_files(pytester) == {"target.html", "evidence.html", "evidence.json"}


def test_artifacts_none_leaves_no_run_directory(pytester):
    project(pytester)
    pytester.runpytest("--itf-target=target.yaml", "--itf-artifacts=none").assert_outcomes(passed=2, deselected=1)
    assert run_files(pytester) == set()


@pytest.mark.parametrize("how", ["option", "environment", "ini"])
def test_artifacts_full_writes_every_file_and_structured_events(pytester, monkeypatch, how):
    project(pytester, ini="[pytest]\nitf_artifacts = full\n" if how == "ini" else "")
    args = ["--itf-target=target.yaml"] + (["--itf-artifacts=full"] if how == "option" else [])
    if how == "environment":
        monkeypatch.setenv("ITF_ARTIFACTS", "full")
    result = pytester.runpytest(*args)
    result.assert_outcomes(passed=2, deselected=1)
    assert "ITF session" in result.stdout.str()
    assert run_files(pytester) >= {"events.jsonl", "plan.json", "claims.json", "run.json", "target.html"}
    assert "test.log" not in run_files(pytester)


# A requirement can sit on a test, its class, its module or its package; a test needs all of them.
SCOPED_TESTS = """
import score.itf as itf


@itf.requires("command")
class TestNeedsACommand:
    def test_one(self, target):
        raise AssertionError("must have been deselected")

    def test_two(self, target):
        raise AssertionError("must have been deselected")


class TestInheritsTheNeed(TestNeedsACommand):
    pass


class TestPlain:
    def test_three(self, target):
        assert target.store.name
"""


def test_a_class_requirement_gates_every_test_in_it_and_in_its_subclasses(pytester):
    project(pytester)
    pytester.makepyfile(test_it=SCOPED_TESTS)
    result = pytester.runpytest("--itf-target=target.yaml", "-rA")
    result.assert_outcomes(passed=1, deselected=4)


def test_a_module_requirement_gates_every_test_in_the_module(pytester):
    project(pytester)
    pytester.makepyfile(
        test_it='import score.itf as itf\n\nitf_requires = itf.requires("command")\n\n\n'
        "def test_one(target):\n    raise AssertionError\n\n\nclass TestA:\n    def test_two(self, target):\n"
        "        raise AssertionError\n",
        test_other="def test_free(target):\n    assert target.store.name\n",
    )
    pytester.runpytest("--itf-target=target.yaml").assert_outcomes(passed=1, deselected=2)


def test_a_package_requirement_gates_every_module_below_it_and_adds_to_theirs(pytester):
    project(pytester)
    pkg = pytester.mkpydir("needs_command")
    (pkg / "__init__.py").write_text('import score.itf as itf\n\nitf_requires = [itf.requires("command")]\n')
    (pkg / "test_inside.py").write_text("def test_inside(target):\n    raise AssertionError\n")
    pytester.makepyfile(test_it="def test_outside(target):\n    assert target.store.name\n")
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-plan")
    out = result.stdout.str()
    assert "test_inside.py::test_inside: deselected: target has no role 'command'" in out
    assert "test_it.py::test_outside: selected" in out


def test_a_secret_in_a_failing_test_is_masked_in_pytest_output_and_the_junit_report(pytester, tmp_path):
    pytester.makepyfile(policy='pytest_plugins = ["vault_parts"]\n')
    pytester.makefile(
        ".yaml",
        target="policies: [policy.py]\ncapabilities:\n  vault:\n    factory: local.vault\n    with:\n      password: hunter2-secret\n",
    )
    pytester.makepyfile(test_it="def test_leak(target):\n    assert target.vault.config['password'] == 'nope'\n")
    report = tmp_path / "junit.xml"
    result = pytester.runpytest("--itf-target=target.yaml", f"--junitxml={report}")
    result.assert_outcomes(failed=1)
    out = result.stdout.str() + result.stderr.str()
    assert "hunter2-secret" not in out and "[redacted]" in out
    assert "hunter2-secret" not in report.read_text()
