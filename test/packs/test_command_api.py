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
from types import SimpleNamespace

from score.itf.packs.docker.command import DockerExec


def test_docker_command_preserves_raw_output():
    output = b"\xff\x00line\r\n"
    calls = []

    def execute(command):
        calls.append(command)
        return 7, output

    platform = SimpleNamespace(container=SimpleNamespace(exec_run=execute))
    assert DockerExec(platform).exec("printf data") == (7, output)
    assert calls == [["/bin/sh", "-c", "printf data"]]
