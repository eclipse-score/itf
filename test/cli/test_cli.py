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
"""`itf plan`, `up`, `doctor` and `diff` on a target file."""

from __future__ import annotations

import json

import pytest

from score.itf.cli import doctor, main as cli
from score.itf.cli.main import main

LOCAL = """
capabilities:
  platform: localhost.platform
  command: localhost.exec
goals:
  - platform.up
"""


def write(tmp_path, name="target.itf.yaml", text=LOCAL):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_plan_prints_roles_with_their_factories_contracts_and_actions(tmp_path, capsys):
    assert main(["plan", write(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "roles (2):" in out
    assert "command (localhost.exec)" in out and "[exec.command]" in out
    assert "platform.up by localhost.start" in out


def test_plan_json_and_output(tmp_path, capsys):
    target = write(tmp_path)
    assert main(["plan", target, "--json", "--output", str(tmp_path / "plan.json")]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert [n["name"] for n in plan["target"]["nodes"]] == ["command", "platform"]
    assert (tmp_path / "plan.json").is_file()


def test_the_configured_target_file_is_used_when_none_is_given(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ITF_TARGET", write(tmp_path))
    assert main(["plan"]) == 0
    assert "command (localhost.exec)" in capsys.readouterr().out


def test_an_override_changes_a_value_by_role(tmp_path, capsys):
    target = write(
        tmp_path,
        text=LOCAL.replace(
            "platform: localhost.platform", "platform:\n    factory: localhost.platform\n    with:\n      root: /one"
        ),
    )
    over = write(tmp_path, "lab.yaml", "capabilities:\n  platform:\n    with:\n      root: /two\n")
    assert main(["plan", target, "--override", over, "--json"]) == 0
    nodes = {n["name"]: n for n in json.loads(capsys.readouterr().out)["target"]["nodes"]}
    assert nodes["platform"]["config"] == {"root": "/two"}


def test_a_target_file_that_does_not_compile_exits_1_with_the_diagnostics(tmp_path, capsys):
    target = write(tmp_path, text="capabilities:\n  command: localhost.exec\n")
    assert main(["plan", target]) == 1
    err = capsys.readouterr().err
    assert "plan failed at gate 1" in err and "Candidates: localhost.platform" in err


def test_a_malformed_target_file_is_reported_not_a_traceback(tmp_path, capsys):
    assert main(["plan", write(tmp_path, text="parts: {}\n")]) == 1
    assert "target file rejected" in capsys.readouterr().err


def test_no_target_file_is_a_clear_message(capsys):
    assert main(["plan"]) == 1
    assert "no target file" in capsys.readouterr().err


class Terminal:
    def isatty(self):
        return True

    def read(self, *_):
        return ""


@pytest.fixture
def console(monkeypatch):
    seen = {}
    monkeypatch.setattr("sys.stdin", Terminal())

    def interact(banner="", readfunc=None, local=None, exitmsg=None):
        seen["local"] = local
        seen["roles"] = local["target"].names()

    monkeypatch.setattr(cli.code, "interact", interact)
    return seen


def test_up_opens_a_console_with_target_and_session_then_closes(tmp_path, console, capsys):
    assert main(["up", write(tmp_path), "--run-dir", str(tmp_path / "run")]) == 0
    assert console["roles"] == ("command", "platform")
    assert console["local"]["session"]._closed
    out = capsys.readouterr().out
    assert "command (localhost.exec)" in out and "evidence:" in out


def test_up_without_a_terminal_brings_up_prints_and_unwinds(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.code, "interact", lambda **_: pytest.fail("no console without a terminal"))
    assert main(["up", write(tmp_path), "--run-dir", str(tmp_path / "run")]) == 0
    assert "command (localhost.exec)" in capsys.readouterr().out


def probes(monkeypatch, **results):
    for key, name in {"engine": "probe_container_engine", "kvm": "probe_kvm", "paramiko": "probe_paramiko"}.items():
        ok = results.get(key, True)
        monkeypatch.setattr(doctor, name, lambda ok=ok, key=key: (ok, f"{key} probe"))


def test_doctor_checks_the_packs_the_target_file_names(tmp_path, monkeypatch, capsys):
    probes(monkeypatch, engine=False)
    target = write(tmp_path, text="capabilities:\n  platform: docker.platform\n")
    assert main(["doctor", target]) == 1
    out = capsys.readouterr().out
    assert "packs: docker" in out and "[ FAIL ] container engine reachable" in out and "DOCKER_HOST" in out


def test_doctor_skips_what_no_listed_pack_needs(tmp_path, monkeypatch, capsys):
    probes(monkeypatch, engine=False)
    assert main(["doctor", write(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "packs: local" in out and "container engine" not in out and "no required check failed" in out


def test_doctor_lists_as_manual_only_what_no_check_covers(tmp_path, monkeypatch, capsys):
    probes(monkeypatch)
    assert main(["doctor", write(tmp_path, text="capabilities:\n  platform: docker.platform\n")]) == 0
    out = capsys.readouterr().out
    assert "[  ok  ] container engine reachable" in out
    assert "[manual] docker: a Docker-compatible daemon" not in out  # the engine check covers it
    assert "[manual] docker: under rootless Podman" in out  # nothing can check that


def test_every_prerequisite_a_check_covers_is_in_its_packs_pack_yaml():
    for check in doctor.CHECKS:
        listed = {item for pack in check.packs for item in doctor.prerequisites(pack)}
        assert set(check.covers) <= listed, f"{check.name} covers {set(check.covers) - listed}, which no pack lists"


def test_diff_compares_two_plans(tmp_path, capsys):
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    assert main(["plan", write(tmp_path), "--json", "--output", str(one)]) == 0
    other = write(tmp_path, "o.yaml", LOCAL.replace("command: localhost.exec", "command: localhost.process"))
    assert main(["plan", other, "--json", "--output", str(two)]) == 0
    capsys.readouterr()
    assert main(["diff", str(one), str(one)]) == 0
    assert main(["diff", str(one), str(two)]) == 1
    assert "command" in capsys.readouterr().out


def test_evidence_of_a_read_only_run_directory_says_where_else_to_write(tmp_path, capsys):
    # Bazel's test outputs are read-only: the page cannot go back into the run directory.
    run = tmp_path / "itf-run"
    run.mkdir()
    (run / "evidence.json").write_text(json.dumps({"run": "itf-run"}), encoding="utf-8")
    run.chmod(0o555)
    try:
        assert main(["evidence", str(run)]) == 1
        assert "--output FILE" in capsys.readouterr().err
        assert main(["evidence", str(run), "--output", str(tmp_path / "page.html")]) == 0
        assert (tmp_path / "page.html").read_text(encoding="utf-8").startswith("<!")
    finally:
        run.chmod(0o755)


def test_under_bazel_run_paths_mean_the_directory_it_was_run_from(tmp_path, monkeypatch, capsys):
    # `bazel run` starts in the runfiles and says where the person was in BUILD_WORKING_DIRECTORY.
    (tmp_path / "test_old.py").write_text("def test_old(target):\n    target.execute('ls')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setenv("BUILD_WORKING_DIRECTORY", str(tmp_path))
    assert main(["compat", "report"]) == 0
    assert "test_old.py:2  target.execute()" in capsys.readouterr().out
