"""The version report joins build provenance, pack metadata and contract majors."""

import json
from argparse import Namespace
from pathlib import Path

from score.itf.cli import main
from score.itf.cli.versions_cmd import _module_metadata, _release_violations, build_report


def test_report_includes_project_locks_pack_and_test_contract_major(tmp_path, monkeypatch):
    monkeypatch.setenv("BUILD_WORKING_DIRECTORY", str(Path(__file__).resolve().parents[2]))
    test_file = tmp_path / "test_versioned.py"
    test_file.write_text(
        "import score.itf as itf\n"
        "@itf.requires('command', contract='exec.command@2', shape=['exec'])\n"
        "def test_command(): ...\n",
        encoding="utf-8",
    )
    report = build_report(Namespace(target=[], override=[], packs="localhost", definitions=[], tests=[str(test_file)]))

    assert report["schema_version"] == 1
    assert report["project"]["module"]["name"] == "score_itf"
    assert report["project"]["distribution"]["loaded_source"].endswith("score/itf/__init__.py")
    assert report["dependencies"]["bazel"]
    assert report["dependencies"]["locks"]
    requirements = next(
        lock for lock in report["dependencies"]["locks"] if lock["path"].startswith("requirements_lock")
    )
    assert any(package["name"] == "pluggy" and package["version"] for package in requirements["packages"])
    localhost = next(pack for pack in report["packs"] if pack["name"] == "localhost")
    assert localhost["version"] == "0.1.0"
    command = next(contract for contract in report["contracts"] if contract["contract"] == "exec.command")
    assert command["tests"] == [
        {"test": f"{test_file}::test_command", "role": "command", "shape": ["exec"], "major": 2}
    ]
    assert any(disagreement["kind"] == "major-mismatch" for disagreement in command["disagreements"])


def test_versions_check_fails_when_test_requires_an_unoffered_major(tmp_path, capsys):
    test_file = tmp_path / "test_versioned.py"
    test_file.write_text(
        "import score.itf as itf\n"
        "@itf.requires('command', contract='exec.command@2', shape=['exec'])\n"
        "def test_command(): ...\n",
        encoding="utf-8",
    )
    result = main.main(["versions", "check", "--packs", "localhost", "--tests", str(test_file), "--json"])
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert result == 1
    assert report["check"]["ok"] is False
    assert report["check"]["complete"] is True
    assert any("expects exec.command@2" in item for item in report["check"]["violations"])


def test_versions_check_can_require_majors_for_a_contract_namespace(capsys):
    result = main.main(["versions", "check", "--packs", "localhost", "--require-major", "exec", "--json"])
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert result == 1
    assert report["check"]["ok"] is False
    assert report["check"]["complete"] is True
    assert any("explicit @major declarations" in item for item in report["check"]["violations"])


def test_module_release_version_is_checked_against_exact_tag_and_clean_tree():
    report = {
        "project": {
            "module": {"name": "score_itf", "version": "1.2.3"},
            "distribution": {"version": "1.2.3", "owns_loaded_source": True},
            "git": {"tag": "v1.2.3", "dirty": False},
        },
        "packs": [{"name": "sample", "version": "0.1.0"}],
        "errors": [],
    }
    assert _release_violations(report, "1.2.3") == []
    report["project"]["git"]["dirty"] = True
    assert _release_violations(report, "1.2.3") == ["tracked or untracked working-tree changes are present"]


def test_versions_check_require_major_includes_state_offers_and_dependencies():
    from score.itf.cli.versions_cmd import _consistency_violations
    from score.itf.contracts import contract_map
    from score.itf.core.engine.publish import PART_ATTR, state

    @state("shell.open@2", after=["shell.ready"], breaks=["shell.old"])
    def open_shell(): ...

    report = {"contracts": [entry.to_json() for entry in contract_map([getattr(open_shell, PART_ATTR)]).values()]}
    problems = _consistency_violations(report, ["shell"])
    assert len(problems) == 2
    assert any("shell.ready requires explicit @major" in problem for problem in problems)
    assert any("shell.old requires explicit @major" in problem for problem in problems)
    assert not any("shell.open requires" in problem for problem in problems)


def test_module_metadata_parses_optional_release_version(tmp_path):
    module = tmp_path / "MODULE.bazel"
    module.write_text('module(name = "score_itf", version = "1.2.3")\n', encoding="utf-8")
    assert _module_metadata(tmp_path) == {"file": "MODULE.bazel", "name": "score_itf", "version": "1.2.3"}


def test_versions_check_reads_strict_protocol_contract_majors(tmp_path, capsys):
    test = tmp_path / "test_strict.py"
    test.write_text(
        "from typing import Protocol\nimport score.itf as itf\n"
        "class CommandAPI(Protocol):\n"
        "    __contract__ = 'exec.command@2'\n"
        "    def exec(self, command: str): ...\n"
        "@itf.requires('command', shape=CommandAPI)\ndef test_command(): ...\n",
        encoding="utf-8",
    )
    result = main.main(["versions", "check", "--packs", "localhost", "--tests", str(test), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert result == 1 and report["check"]["complete"] is True
    assert any("expects exec.command@2" in item for item in report["check"]["violations"])


def test_versions_check_is_incomplete_for_unresolved_imported_protocols(tmp_path, capsys):
    test = tmp_path / "test_imported.py"
    test.write_text(
        "from consumer import CommandAPI\nimport score.itf as itf\n"
        "@itf.requires('command', shape=CommandAPI)\ndef test_command(): ...\n",
        encoding="utf-8",
    )
    result = main.main(["versions", "check", "--packs", "localhost", "--tests", str(test), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert result == 2 and report["check"]["complete"] is False
    assert any("cannot statically resolve Protocol shape CommandAPI" in error for error in report["errors"])
