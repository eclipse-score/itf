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
"""Every target file the repository ships compiles: both gates and every setting, with placeholders for the values
only a test run has. It covers the target files no build compiles, such as the manual QEMU ones."""

import os
import re
import runpy
import subprocess
from pathlib import Path

import pytest

PACKS = ("core_dump", "dlt", "docker", "localhost", "net", "pcap", "ping", "qemu", "serial", "sim", "ssh")
ROOTS = (Path("test/integration/targets"), Path("score/itf/compat/targets"))


def target_files() -> list[Path]:
    return sorted(path for root in ROOTS for path in root.rglob("*.itf.yaml"))


@pytest.mark.parametrize("target_file", target_files(), ids=str)
def test_the_target_file_compiles(target_file, tmp_path):
    args = [os.environ["PLANNER"], "--target", str(target_file), "--out", str(tmp_path / "plan.json")]
    args += [arg for pack in PACKS for arg in ("--pack", pack)]
    done = subprocess.run(args, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_there_are_target_files_to_compile():
    assert len(target_files()) >= 10


@pytest.fixture
def ubuntu_policy():
    return runpy.run_path("test/integration/targets/ubuntu/policy.py")


class _UbuntuConsole:
    def __init__(self, prompt="login:", *, login_delay=0, accepts_login=True):
        self.prompt = prompt
        self.login_delay = login_delay
        self.accepts_login = accepts_login
        self.open = True
        self.responsive = True
        self.status = 0
        self.history = ["ITF_CONSOLE_SHELL_READY", "root@ubuntu:~# "]
        self.writes = []
        self.commands = []

    def is_open(self):
        return self.open

    def mark(self):
        return len(self.history)

    def write(self, text):
        self.writes.append(text)
        if text == "root":
            assert self.prompt == "login:"
            if self.accepts_login:
                self.prompt = "pending" if self.login_delay else "#"
        elif text == "":
            if self.prompt == "pending":
                self.login_delay -= 1
                if self.login_delay == 0:
                    self.prompt = "#"
            if self.prompt not in (None, "pending"):
                self.history.append(f"ubuntu {self.prompt} ")
        else:
            pytest.fail(f"unexpected console input: {text!r}")

    def wait_for(self, pattern, timeout=30, *, since=None, regex=False):
        assert regex and since is not None
        return next((line for line in self.history[since:] if re.search(pattern, line)), None)

    def run(self, command, timeout=30):
        assert self.prompt == "#", "commands must not be sent to a login prompt"
        self.commands.append(command)
        if not self.responsive:
            raise TimeoutError("shell stopped responding")
        return self.status, ""


@pytest.mark.parametrize("prompt,login_delay", [("login:", 0), ("login:", 3), ("#", 0)])
def test_ubuntu_console_login_synchronizes_with_the_prompt(ubuntu_policy, prompt, login_delay):
    console = _UbuntuConsole(prompt, login_delay=login_delay)
    ubuntu_policy["login_ubuntu_console"](console)
    assert console.writes.count("root") == (prompt == "login:")
    assert console.commands == ["true"]
    assert ubuntu_policy["ubuntu_console_has_shell"](console)
    assert console.commands == ["true", "true"]


@pytest.mark.parametrize("prompt", [None, "login:"])
def test_ubuntu_console_probe_ignores_historical_readiness(ubuntu_policy, prompt):
    console = _UbuntuConsole(prompt)
    assert not ubuntu_policy["ubuntu_console_has_shell"](console)
    assert console.commands == []
    assert all(text == "" for text in console.writes)


@pytest.mark.parametrize("responsive,status", [(False, 0), (True, 1)])
def test_ubuntu_console_probe_checks_a_fresh_command(ubuntu_policy, responsive, status):
    console = _UbuntuConsole("#")
    assert ubuntu_policy["ubuntu_console_has_shell"](console)
    console.responsive, console.status = responsive, status
    assert not ubuntu_policy["ubuntu_console_has_shell"](console)
    assert console.commands == ["true", "true"]


def test_ubuntu_console_probe_handles_a_closed_console(ubuntu_policy):
    console = _UbuntuConsole("#")
    console.open = False
    assert not ubuntu_policy["ubuntu_console_has_shell"](console)
    assert not console.writes and not console.commands


@pytest.mark.parametrize("prompt", [None, "login:"])
def test_ubuntu_console_login_fails_without_a_responsive_shell(ubuntu_policy, prompt):
    console = _UbuntuConsole(prompt, accepts_login=False)
    with pytest.raises(RuntimeError, match="Ubuntu serial console"):
        ubuntu_policy["login_ubuntu_console"](console)
    assert console.commands == []


def test_ubuntu_console_prompt_accepts_terminal_control_sequences(ubuntu_policy):
    console = _UbuntuConsole("# \x1b[?2004l")
    assert ubuntu_policy["_prompt"](console) == "#"
