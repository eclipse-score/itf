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
"""Map pytest discovery and lifecycle onto an ITF session.

Structured event capture is a companion plugin; pytest owns the text log, while this module owns resolution,
gating, bring-up and unwind.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from types import ModuleType

import pluggy
import pytest

from ... import gating as itf_gating
from ...engine.failure import banner
from ...engine.hooks import HOOK_NAMES, ITFHookSpecs, implements_itf_hooks
from ...engine.metadata import LOCAL_PACK, contributor_metadata, pack_name
from ...engine import secrets
from ...engine.registry import CrossContributorImport, is_contributor
from ...frontends import target_source
from .. import definitions as contract_definitions
from ...session import (
    ARTIFACTS,
    ConfigValidationFailed,
    DescribeResult,
    NotReady,
    ResolutionFailed,
    Session,
    TargetNameClash,
)

pytest_plugins = ["score.itf.core.adapters.pytest.run_logging"]
_pytest_hookspec = pluggy.HookspecMarker("pytest")
logger = logging.getLogger(__name__)


class _AdapterHookSpecs:
    @_pytest_hookspec
    def pytest_itf_session_created(self, config, session, contributors):
        """An ITF session exists but has not resolved or accessed its target yet."""


def pytest_addhooks(pluginmanager):
    """Declare the itf_* hooks to pytest too, so `@pytest.hookimpl` on them is accepted."""
    for name in HOOK_NAMES:
        _pytest_hookspec(getattr(ITFHookSpecs, name))
    pluginmanager.add_hookspecs(ITFHookSpecs)
    pluginmanager.add_hookspecs(_AdapterHookSpecs)


def pytest_addoption(parser):
    group = parser.getgroup("itf")
    group.addoption(
        "--itf-plan",
        action="store_true",
        default=False,
        dest="itf_plan",
        help="resolve and print the plan and gating; run nothing",
    )
    group.addoption(
        "--itf-fresh",
        action="store_true",
        default=False,
        dest="itf_fresh",
        help="run every planned action, ignoring what probes observe",
    )
    group.addoption(
        "--itf-keep",
        action="store_true",
        default=False,
        dest="itf_keep",
        help="run teardown hooks but leave what was built running (no unwind)",
    )
    group.addoption(
        "--itf-bring-up-attempts",
        type=int,
        default=1,
        help="how often bring-up may plan again when a step fails because a state that held stopped holding "
        "(a machine that died while booting); any other failure ends it at once (default: 1, no retry)",
    )
    group.addoption(
        "--itf-strict-gating",
        action="store_true",
        default=False,
        dest="itf_strict_gating",
        help="reject incompatible or unverifiable API requirements during collection, before bring-up",
    )
    group.addoption(
        "--itf-run-dir",
        action="store",
        default=None,
        dest="itf_run_dir",
        help="where ITF run artifacts go (default: $TEST_UNDECLARED_OUTPUTS_DIR/itf-run "
        "under Bazel, else itf-run/ in the pytest root directory)",
    )
    group.addoption(
        "--itf-artifacts",
        action="store",
        default=None,
        choices=ARTIFACTS,
        dest="itf_artifacts",
        help="what a run leaves in its run directory: none, standard (default: plan and evidence) or full "
        "(all artifacts, including structured events). Text logs remain in pytest output. Also ITF_ARTIFACTS or "
        "`itf_artifacts` in pytest.ini",
    )
    group.addoption(
        "--itf-target",
        action="store",
        default=None,
        dest="itf_target",
        help="the target file: a YAML/JSON file (or inline text). Also ITF_TARGET, `itf_target` in "
        "pytest.ini or `[tool.itf] target` in pyproject.toml",
    )
    group.addoption(
        "--itf-override",
        action="append",
        default=None,
        dest="itf_override",
        help="an override file: a target file holding only what changes, merged by role over the target file "
        "(repeatable). Also ITF_OVERRIDE, `itf_override` in pytest.ini or `[tool.itf] override` in pyproject.toml",
    )
    # Declared so that pytest knows them; target_source.discover reads them (with the environment and
    # pyproject.toml) for every front alike.
    parser.addini("itf_target", "the target file: a YAML/JSON file, relative to the project", default="")
    parser.addini("itf_artifacts", "what a run leaves in its run directory: none, standard or full", default="")
    parser.addini("itf_override", "override files, relative to the project, separated by os.pathsep", default="")


def _declares_itf_code(module: ModuleType) -> bool:
    return implements_itf_hooks(module) or (
        is_contributor(module) and pack_name(contributor_metadata(module)) == LOCAL_PACK
    )


def contributors_from_pytest(pluginmanager) -> list[tuple[ModuleType, str]]:
    """The pytest plugins of packs that implement an ITF hook. ITF code anywhere else (a
    conftest, a plugin outside any pack) is an error: conftests are pytest's, for fixtures. Packs load from the
    labels of the target file, not from pytest."""
    entries = []
    for module in [p for p in pluginmanager.get_plugins() if isinstance(p, ModuleType)]:
        if not _declares_itf_code(module):
            continue
        if Path(getattr(module, "__file__", "") or "").name == "conftest.py" or not _in_a_pack(module):
            raise pytest.UsageError(
                _section(
                    "ITF: ITF code outside the policy",
                    f"{module.__file__} declares ITF hooks or local parts; list their policy file in the target's "
                    "policies. Conftests hold pytest fixtures only.",
                )
            )
        entries.append((module, "plugin"))
    return entries


def _in_a_pack(module: ModuleType) -> bool:
    return contributor_metadata(module) is not None


def _discover(config) -> target_source.Discovered:
    """The target file and the override files, by the one discovery every front uses."""
    try:
        return target_source.discover(
            config.getoption("itf_target"),
            config.getoption("itf_override") or (),
            root=config.rootpath,
            target_file_origin="--itf-target",
            override_origin="--itf-override",
        )
    except target_source.TargetSourceError as exc:
        logger.error("itf: %s", exc)
        raise pytest.UsageError(_section("ITF: no usable target file", str(exc))) from exc


def _definitions() -> dict:
    """contract name -> Definition from the optional contract library, when it is installed; else nothing."""
    try:
        return contract_definitions.definitions()
    except ValueError as exc:  # the library found definitions that do not merge
        logger.error("itf: contract definitions rejected: %s", exc)
        raise pytest.UsageError(_section("ITF: contract definitions rejected", str(exc))) from exc


def artifact_level(config) -> str:
    """--itf-artifacts, else ITF_ARTIFACTS, else `itf_artifacts` in pytest.ini, else standard."""
    value = config.getoption("itf_artifacts") or os.environ.get("ITF_ARTIFACTS") or config.getini("itf_artifacts")
    value = value or "standard"
    if value not in ARTIFACTS:
        raise pytest.UsageError(f"itf: artifacts {value!r}: use one of {', '.join(ARTIFACTS)}")
    return value


def _run_dir(config) -> Path:
    explicit = config.getoption("itf_run_dir")
    if explicit:
        return Path(explicit)
    bazel_outputs = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")
    if bazel_outputs:
        return Path(bazel_outputs) / "itf-run"
    return Path(str(config.rootpath)) / "itf-run"


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    config._itf_session = None

    found = _discover(config)
    contributors = contributors_from_pytest(config.pluginmanager)
    if found.target_file is None and not any(implements_itf_hooks(module) for module, _ in contributors):
        return

    session = Session(
        contributors=contributors,
        target=found.target_file,
        overrides=found.overrides,
        plan_only=bool(config.getoption("itf_plan")),
        gating="fail" if config.getoption("itf_strict_gating") else "skip",
        reuse="fresh" if config.getoption("itf_fresh") else "probe",
        on_exit="keep" if config.getoption("itf_keep") else "unwind",
        definitions=_definitions(),
        run_dir=_run_dir(config),
        artifacts=artifact_level(config),
        bring_up_attempts=config.getoption("itf_bring_up_attempts"),
    )
    config._itf_session = session
    config.hook.pytest_itf_session_created(config=config, session=session, contributors=contributors)
    try:
        session.resolve()
    except ResolutionFailed as exc:
        raise pytest.UsageError(_section(f"ITF: plan failed at gate {exc.gate}", exc.rendered)) from exc
    except (ConfigValidationFailed, TargetNameClash) as exc:
        logger.error("itf: %s", exc)
        raise pytest.UsageError(_section("ITF: target file rejected", str(exc))) from exc
    except (CrossContributorImport, TypeError, ValueError) as exc:  # TargetFileError is a ValueError
        logger.error("itf: %s: %s", type(exc).__name__, exc)
        raise pytest.UsageError(_section("ITF: target file rejected", f"{type(exc).__name__}: {exc}")) from exc
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None and session.packs:
        # the header is written before resolve, which loads the packs; the run log names them as they load
        reporter.write_line("packs: " + ", ".join(f"{name} {version}" for name, version, _ in session.packs))


def _section(title: str, body: str) -> str:
    """A pytest-style `=== title ===` block, for errors raised before the terminal reporter is writing."""
    width = shutil.get_terminal_size((100, 20)).columns
    return f"\n{banner(title, width)}\n{body}\n{'=' * width}"


def _show(config, failure) -> None:
    """Print a failure report as its own section, the way pytest prints `=== FAILURES ===`."""
    text = failure.render()
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        print(text)
        return
    reporter.write_line("")
    for line in text.splitlines():
        reporter.write_line(line, red=line.startswith("="), bold=line.startswith("="))


def pytest_collection_modifyitems(config, items):
    session = getattr(config, "_itf_session", None)
    if session is None:
        return
    requirements = {}
    for item in items:
        fn = getattr(item, "obj", None)
        requirements[item.nodeid] = itf_gating.requirements_of(
            fn, getattr(item, "cls", None), getattr(item, "module", None)
        )
    decisions = session.select(requirements)
    if session.gating == "fail" and session.preflight_report.blocking:
        raise pytest.UsageError(session.preflight_report.render(blocking_only=True))
    _deselect(config, items, decisions)
    if config.getoption("itf_plan"):
        _print_plan(session)
        pytest.exit("itf: --itf-plan, nothing run", returncode=0)


def _deselect(config, items, decisions) -> None:
    kept, dropped = [], []
    for item in items:
        decision = decisions.get(item.nodeid)
        (dropped if decision is not None and not decision.selected else kept).append(item)
    if dropped:
        items[:] = kept
        config.hook.pytest_deselected(items=dropped)


def _print_plan(session) -> None:
    if session.target_source is not None:
        print(f"Target file: {session.target_source.describe()}")
    print(DescribeResult(session).render())
    print("Gating:")
    for test_id, decision in session.gating_decisions:
        state = "selected" if decision.selected else f"deselected: {decision.reason}"
        print(f"  {test_id}: {state}")
    if session.preflight_report is not None:
        print(session.preflight_report.render())


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A test's failure text and captured output, with the session's secrets masked: they reach the terminal,
    the JUnit report and any other reporter from here."""
    outcome = yield
    report = outcome.get_result()
    if report.longrepr is not None:
        text = str(report.longrepr)
        masked = secrets.mask(text)
        if masked != text:
            report.longrepr = masked
    report.sections = [(title, secrets.mask(content)) for title, content in report.sections]


def _itf_session_of(request):
    session = getattr(request.config, "_itf_session", None)
    if session is None:
        pytest.fail(
            "itf: no target file: none is configured (--itf-target, ITF_TARGET, the itf_target ini "
            "option or [tool.itf] target), so there is no target",
            pytrace=False,
        )
    return session


@pytest.fixture(scope="session")
def target(request):
    return _itf_session_of(request).target


@pytest.fixture(scope="session")
def session(request):
    return request.config._itf_session


def pytest_collection_finish(session):
    """Bring-up happens after collection/gating and before the test loop."""
    config = session.config
    itf_session = getattr(config, "_itf_session", None)
    if itf_session is None or itf_session.plan_only or config.option.collectonly:
        return
    if (
        itf_session.gating == "fail"
        and itf_session.preflight_report is not None
        and itf_session.preflight_report.blocking
    ):
        return
    if not session.items:
        return
    config._itf_brought_up = True
    try:
        itf_session.bring_up()
    except NotReady as exc:
        if exc.failure is not None:
            _show(config, exc.failure)
        itf_session.close()
        _show_close_problems(config, itf_session)
        pytest.exit(f"itf: session not ready: {exc}", returncode=1)


def _show_close_problems(config, itf_session) -> None:
    # pytest_sessionfinish runs again after pytest.exit: report the closing problems once.
    problems = None if getattr(config, "_itf_close_shown", False) else itf_session.close_problems()
    config._itf_close_shown = True
    if problems is not None:
        _show(config, problems)


def pytest_sessionfinish(session):
    config = session.config
    itf_session = getattr(config, "_itf_session", None)
    if itf_session is not None and getattr(config, "_itf_brought_up", False):
        itf_session.close()
        _show_close_problems(config, itf_session)
