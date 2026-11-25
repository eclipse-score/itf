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
import pytest

from score.itf.packs.docker import process as docker_process
from score.itf.packs.docker.command import DockerExec


class CompletedProcess:
    def __init__(self):
        self.timeout = None
        self.stopped = False

    def wait(self, timeout_s):
        self.timeout = timeout_s
        return 7

    def stop(self):
        self.stopped = True

    def get_output_bytes(self):
        return b"out\x00\xff"


class TimedOutProcess:
    def __init__(self):
        self.stopped = False

    def wait(self, timeout_s):
        assert timeout_s == 0.01
        raise docker_process._DockerProcessTimeout("expired")

    def stop(self):
        self.stopped = True


def test_docker_exec_uses_managed_process_and_preserves_binary_output(monkeypatch):
    process = CompletedProcess()
    spawned = []

    def spawn(self, binary_path, args=None, cwd="/", **kwargs):
        spawned.append((binary_path, args, cwd))
        return process

    monkeypatch.setattr(docker_process.DockerProcess, "spawn", spawn)

    result = DockerExec(object()).exec("printf output", timeout=3.5)

    assert result == (7, b"out\x00\xff")
    assert process.timeout == 3.5
    assert not process.stopped
    assert spawned == [("/bin/sh", ["-c", "printf output"], "/")]


def test_docker_exec_stops_only_its_command_when_timeout_expires(monkeypatch):
    process = TimedOutProcess()
    monkeypatch.setattr(docker_process.DockerProcess, "spawn", lambda *args, **kwargs: process)

    with pytest.raises(TimeoutError, match="did not finish within 0.01 seconds"):
        DockerExec(object()).exec("sleep 5", timeout=0.01)

    assert process.stopped
