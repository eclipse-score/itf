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
"""The planning benchmark: a report on stdout, or a Markdown file with a summary table and its link on stdout;
--check fails on a threshold or a target file that does not plan."""

import pytest

from tools.benchmark import plan_bench

FAST = ["--scale", "scopes", "--sizes", "2", "--reps", "2", "--no-cold"]


def test_without_report_the_whole_report_goes_to_stdout(capsys):
    assert plan_bench.main(FAST) == 0
    out = capsys.readouterr().out
    for section in ("Summary", "Warm plan by phase (median ms)", "Median share of a warm plan", "Thresholds"):
        assert section in out
    assert "scopes-2" in out and "No threshold exceeded." in out
    assert "report:" not in out


def test_with_report_the_file_has_the_report_and_stdout_the_summary_and_its_link(capsys, tmp_path):
    report = tmp_path / "bench.md"
    assert plan_bench.main([*FAST, "--report", str(report)]) == 0
    out = capsys.readouterr().out
    text = report.read_text()
    assert text.startswith("# ITF planning benchmark") and "| scopes-2 |" in text and "## Thresholds" in text
    assert "scopes-2" in out and f"report: {report.resolve().as_uri()}" in out
    assert "Warm plan by phase" not in out


def test_check_fails_when_a_threshold_is_exceeded(capsys, monkeypatch):
    monkeypatch.setitem(plan_bench.THRESHOLDS, "warm_ms", (0.0, "a running process plans one target file"))
    assert plan_bench.main(FAST) == 0  # without --check it only reports
    assert plan_bench.main([*FAST, "--check"]) == 1
    assert "Exceeded:" in capsys.readouterr().out


def test_a_target_file_that_does_not_plan_is_a_row_and_the_others_still_run(capsys, tmp_path):
    broken = tmp_path / "broken.itf.yaml"
    broken.write_text("capabilities:\n  command: nosuchpack.exec\n")
    assert plan_bench.main([str(broken), *FAST]) == 0
    assert plan_bench.main([str(broken), *FAST, "--check"]) == 1
    out = capsys.readouterr().out
    assert "error" in out and "scopes-2" in out


def test_something_to_measure_is_required():
    with pytest.raises(SystemExit) as exc:
        plan_bench.main([])
    assert exc.value.code == 2
