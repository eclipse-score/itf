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
"""What the project had before ITF, kept for comparison with the facade in conftest.py; nothing imports it.

The class knew how to reach one kind of machine (a container, through the docker command line). Every new kind
of machine meant another class, and the bring-up order lived in a fixture.
"""

import subprocess


class Ecu:
    def __init__(self, container: str):
        self.container = container

    def run(self, cmd: str) -> tuple[int, str]:
        done = subprocess.run(["docker", "exec", self.container, "sh", "-c", cmd], capture_output=True, text=True)
        return done.returncode, done.stdout + done.stderr

    def push(self, local_path: str, remote_path: str) -> None:
        subprocess.run(["docker", "cp", local_path, f"{self.container}:{remote_path}"], check=True)

    def pull(self, remote_path: str, local_path: str) -> None:
        subprocess.run(["docker", "cp", f"{self.container}:{remote_path}", local_path], check=True)

    def has_capability(self, name: str) -> bool:
        return name in {"exec", "flash"}
