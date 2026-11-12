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

import os

import leaky_parts

from score.itf.core import Session
from score.itf.core.process import ProcessWrapper

LEAKY = "capabilities:\n  leak: local.leaky\n"


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
