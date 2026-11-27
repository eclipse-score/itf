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
"""`itf compat report` lists what a suite still uses of the original API, with the replacement of each, from the
source; `itf compat target` writes the target file the original options make."""

import yaml

from score.itf.cli.main import main

OLD_TEST = """
import score.itf
from score.itf.plugins.dlt.dlt_receive import DltReceive


@score.itf.plugins.core.requires_capabilities("exec", "file_transfer")
def test_old(target, docker_configuration):
    code, out = target.execute("uname -a")
    target.upload("a", "/tmp/a")


def test_new(target):
    target.command.exec("uname -a")
"""
OLD_BUILD = """py_itf_test(
    name = "t",
    args = ["--docker-image=ubuntu:24.04"],
    plugins = ["//score/itf/plugins:docker_plugin"],
)
"""


def test_report_names_each_original_use_with_its_replacement(tmp_path, capsys):
    (tmp_path / "test_old.py").write_text(OLD_TEST)
    (tmp_path / "BUILD").write_text(OLD_BUILD)
    assert main(["compat", "report", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "test_old.py:3  from score.itf.plugins.dlt.dlt_receive import ..." in out
    assert 'requires_capabilities(...)  ->  @itf.requires("command") @itf.requires("files")' in out
    assert "fixture docker_configuration" in out
    assert "target.execute()  ->  target.command.exec(cmd)" in out and "target.upload()" in out
    assert "//score/itf/plugins:docker_plugin" in out and "--docker-image" in out
    assert "7 use(s) of the original API" in out
    assert "target.command" not in out.split("->")[0]  # the new-style test is not reported


def test_a_migrated_suite_has_nothing_left(tmp_path, capsys):
    (tmp_path / "test_new.py").write_text("def test_new(target):\n    target.command.exec('ls')\n")
    assert main(["compat", "report", str(tmp_path)]) == 0
    assert "nothing left to migrate" in capsys.readouterr().out


def test_target_writes_the_target_file_the_options_make(tmp_path, capsys):
    out = tmp_path / "targets"
    assert main(["compat", "target", "--docker-image", "ubuntu:24.04", "--out", str(out)]) == 0
    doc = yaml.safe_load((out / "target.itf.yaml").read_text())
    assert doc["capabilities"]["platform"]["with"]["image"] == "ubuntu:24.04"
    assert (out / "policy.py").is_file()
    assert doc["policies"] == [str((out / "policy.py").resolve())]
    from score.itf.core.frontends.target_source import load_policies

    assert len(load_policies(doc["policies"])) == 1
    env = (out / ".env.example").read_text()
    assert "LEGACY_SSH_PASSWORD=" not in env and "LEGACY_DOCKER_IMAGE" not in env


def test_target_needs_the_options_the_original_plugins_needed(tmp_path, capsys):
    assert main(["compat", "target", "--out", str(tmp_path)]) == 2
    assert "--docker-image or --qemu-config" in capsys.readouterr().out
