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
"""A session reaps the host processes started on its behalf, and only those."""

import concurrent.futures
import os
import sys

import leaky_parts
import pytest

from score.itf.core import Session
from score.itf.core.process import ProcessWrapper
from score.itf.core.process import process_wrapper

LEAKY = "capabilities:\n  leak: local.leaky\n"


def test_keep_rejects_unobservable_teardown_before_construction(pytester):
    pytester.makepyfile(policy='pytest_plugins = ["kv_parts"]\n')
    pytester.makefile(".yaml", target="policies: [policy.py]\ncapabilities:\n  store: local.store\n")
    pytester.makepyfile(test_it="def test_target(target):\n    assert target.store\n")
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-keep")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "--itf-keep refused" in result.stderr.str()
    assert "observes=True" in result.stderr.str()


def test_keep_leaves_an_observable_target_running(pytester, tmp_path):
    root = tmp_path / "bench"
    pytester.makefile(
        ".yaml",
        target=f"capabilities:\n  platform:\n    factory: localhost.platform\n    with:\n      root: {root}\n"
        "goals:\n  - platform.up\n",
    )
    pytester.makepyfile(test_it="def test_target(target):\n    assert target.platform is not None\n")
    result = pytester.runpytest("--itf-target=target.yaml", "--itf-keep")
    result.assert_outcomes(passed=1)
    assert root.is_dir()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return not os.path.exists(f"/proc/{pid}") or open(f"/proc/{pid}/stat", encoding="utf-8").read().split()[2] != "Z"


def test_close_reaps_what_its_own_session_started_and_leaves_the_neighbours_alone(tmp_path):
    first = Session([leaky_parts], target=LEAKY, run_dir=tmp_path / "first").resolve()
    second = Session([leaky_parts], target=LEAKY, run_dir=tmp_path / "second").resolve()
    # built after both resolved: each process belongs to the session whose code built it
    mine, theirs = first.target.leak.pid, second.target.leak.pid
    try:
        first.close()
        assert not alive(mine) and alive(theirs)
        assert first.close_problems() is not None  # the leak is reported
    finally:
        second.close()
        ProcessWrapper.reap()
    assert not alive(theirs)


def test_reap_without_an_owner_stops_everything_as_the_exit_handler_does():
    one = ProcessWrapper("sleep", ["30"]).start_process()
    with ProcessWrapper.owned_by(object()):
        two = ProcessWrapper("sleep", ["30"]).start_process()
    assert len(ProcessWrapper.reap()) == 2
    assert not one.is_running() and not two.is_running()


def test_an_owner_is_set_while_a_session_runs_and_released_when_it_closes(tmp_path):
    session = Session([leaky_parts], target=LEAKY, run_dir=tmp_path / "run").resolve()
    process = ProcessWrapper("sleep", ["30"]).start_process()  # test code, between resolve and close
    try:
        other = object()
        assert ProcessWrapper.reap(owner=other) == ()  # not theirs
        assert process.is_running()
        session.close()
        assert not process.is_running()
    finally:
        ProcessWrapper.reap()
    after = ProcessWrapper("sleep", ["30"]).start_process()  # started once the session is gone: nobody's
    try:
        assert ProcessWrapper.reap(owner=session) == ()
    finally:
        ProcessWrapper.reap()
    assert not after.is_running()


def test_nested_sessions_restore_the_previous_process_owner(tmp_path):
    outer = Session([leaky_parts], target=LEAKY, run_dir=tmp_path / "outer").resolve()
    inner = Session([leaky_parts], target=LEAKY, run_dir=tmp_path / "inner").resolve()
    inner.close()
    process = ProcessWrapper("sleep", ["30"]).start_process()
    try:
        assert process._owner is outer
    finally:
        outer.close()
        ProcessWrapper.reap()
    assert not process.is_running()


def test_process_started_in_a_worker_thread_can_be_explicitly_owned_by_a_session(tmp_path):
    session = Session([leaky_parts], target=LEAKY, run_dir=tmp_path / "thread").resolve()

    def start_owned_process():
        with ProcessWrapper.owned_by(session):
            return ProcessWrapper("sleep", ["30"]).start_process()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        process = executor.submit(start_owned_process).result(timeout=10)
    assert process._owner is session

    session.close()

    assert not process.is_running()


def test_stopping_the_last_process_in_a_worker_thread_does_not_restore_signals_there():
    wrapper = ProcessWrapper("sleep", ["30"]).start_process()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(wrapper.kill_process).result(timeout=10)
        assert not wrapper.is_running()
        assert ProcessWrapper.live() == ()
        assert process_wrapper._PENDING_UNINSTALL
        next_process = ProcessWrapper("sleep", ["30"]).start_process()
        assert process_wrapper._HANDLER_INSTALLED and not process_wrapper._PENDING_UNINSTALL
        next_process.kill_process()
        assert not process_wrapper._HANDLER_INSTALLED
    finally:
        wrapper.kill_process()
        process_wrapper._uninstall_handler()


def test_run_kills_its_child_when_interrupted(monkeypatch):
    real_popen = process_wrapper.subprocess.Popen
    children = []

    def interrupted_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)

        def interrupt(*_args, **_kwargs):
            raise KeyboardInterrupt

        process.communicate = interrupt
        children.append(process)
        return process

    monkeypatch.setattr(process_wrapper.subprocess, "Popen", interrupted_popen)
    with pytest.raises(KeyboardInterrupt):
        ProcessWrapper.run(sys.executable, ["-c", "import time; time.sleep(30)"])
    assert children and children[0].poll() is not None
