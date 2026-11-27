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
"""Target discovery and explicit policy loading shared by every front."""

import os
import sys
from dataclasses import fields

import pytest

from score.itf import Session
from score.itf.core.frontends import target_source as source
from score.itf.core.frontends.target_source import TargetSourceError, discover, load_policy, read_document


def write(path, text="capabilities: {}\n"):
    path.write_text(text, encoding="utf-8")
    return str(path)


def found(root, explicit=None, overrides=(), **kw):
    return discover(explicit, overrides, root=root, environ=kw.pop("environ", {}), **kw)


def test_the_order_is_explicit_then_environment_then_ini_then_pyproject(tmp_path):
    explicit, from_env, from_ini, from_toml = (write(tmp_path / f"{n}.yaml") for n in ("a", "b", "c", "d"))
    (tmp_path / "pytest.ini").write_text("[pytest]\nitf_target = c.yaml\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.itf]\ntarget = "d.yaml"\n', encoding="utf-8")
    env = {"ITF_TARGET": from_env}
    hit = found(tmp_path, explicit, environ=env, target_file_origin="--itf-target").target_file
    assert (hit.value, hit.origin) == (explicit, "--itf-target")
    hit = found(tmp_path, environ=env).target_file
    assert (hit.value, hit.origin) == (from_env, "ITF_TARGET")
    hit = found(tmp_path).target_file
    assert (hit.value, hit.origin) == (from_ini, "pytest.ini itf_target")
    (tmp_path / "pytest.ini").unlink()
    hit = found(tmp_path).target_file
    assert hit.value == from_toml and hit.origin == "pyproject.toml [tool.itf] target"


def test_the_ini_is_pytest_ini_or_pytest_options_in_pyproject(tmp_path):
    target = write(tmp_path / "x.yaml")
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\nitf_target = "x.yaml"\n', encoding="utf-8")
    hit = found(tmp_path).target_file
    assert hit.value == target and "[tool.pytest.ini_options] itf_target" in hit.origin


def test_nothing_configured_is_nothing(tmp_path):
    result = found(tmp_path)
    assert (result.target_file, result.overrides) == (None, ())
    assert [field.name for field in fields(result)] == ["target_file", "overrides"]


def test_a_relative_path_is_tried_against_the_working_directory_then_the_root(tmp_path, monkeypatch):
    root, elsewhere = tmp_path / "root", tmp_path / "elsewhere"
    root.mkdir()
    elsewhere.mkdir()
    write(root / "c.yaml")
    monkeypatch.chdir(elsewhere)
    assert found(root, "c.yaml").target_file.value == str(root / "c.yaml")
    write(elsewhere / "c.yaml")
    assert found(root, "c.yaml").target_file.value == str(elsewhere / "c.yaml")
    # a value from a configuration file is relative to that file's directory
    (root / "pytest.ini").write_text("[pytest]\nitf_target = c.yaml\n", encoding="utf-8")
    assert found(root).target_file.value == str(root / "c.yaml")


def test_a_value_may_be_inline_text(tmp_path):
    hit = found(tmp_path, "capabilities:\n  a: b.c\n").target_file
    assert hit.is_inline and "<inline>" in hit.describe()


def test_a_value_that_is_neither_file_nor_yaml_is_an_error_saying_where_it_looked(tmp_path):
    with pytest.raises(TargetSourceError, match="not an existing file and not inline YAML/JSON text"):
        found(tmp_path, "missing.yaml", target_file_origin="--itf-target")


def test_overrides_come_from_the_runner_then_the_environment_then_ini_then_pyproject_with_os_pathsep(tmp_path):
    base, one, two = (write(tmp_path / f"{n}.yaml") for n in ("base", "one", "two"))
    assert [s.value for s in found(tmp_path, base, [one, two]).overrides] == [one, two]
    env = {"ITF_OVERRIDE": os.pathsep.join([one, two])}
    assert [s.value for s in found(tmp_path, base, environ=env).overrides] == [one, two]
    (tmp_path / "pytest.ini").write_text(f"[pytest]\nitf_override = one.yaml{os.pathsep}two.yaml\n", encoding="utf-8")
    assert [s.value for s in found(tmp_path, base).overrides] == [one, two]
    (tmp_path / "pytest.ini").unlink()
    (tmp_path / "pyproject.toml").write_text('[tool.itf]\noverride = "one.yaml"\n', encoding="utf-8")
    assert [s.value for s in found(tmp_path, base).overrides] == [one]


def test_override_files_without_a_target_file_are_an_error(tmp_path):
    with pytest.raises(TargetSourceError, match="override files need a target file"):
        found(tmp_path, overrides=[write(tmp_path / "lab.yaml")])


@pytest.mark.parametrize("inline", [False, True])
def test_undeclared_policies_beside_the_target_and_in_the_cwd_are_ignored(tmp_path, monkeypatch, inline):
    project, lab = tmp_path / "project", tmp_path / "lab"
    project.mkdir()
    lab.mkdir()
    monkeypatch.chdir(project)
    target = write(lab / "lab.itf.yaml")
    for directory in (project, lab):
        write(directory / "policy.py", "raise AssertionError('undeclared policy imported')\n")
    discovered = found(project, "capabilities: {}\n" if inline else target)
    assert [field.name for field in fields(discovered)] == ["target_file", "overrides"]
    Session(target=discovered.target_file).resolve()


def test_target_files_do_not_inherit_policies_from_parent_directories(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "targets" / "docker").mkdir(parents=True)
    monkeypatch.chdir(project)
    target = write(project / "targets" / "docker" / "docker.itf.yaml")
    write(project / "targets" / "policy.py", "raise AssertionError('parent policy imported')\n")
    Session(target=found(project, target).target_file).resolve()


def test_a_policy_loads_once_under_a_name_of_its_own(tmp_path):
    first, second = tmp_path / "a" / "policy.py", tmp_path / "b" / "policy.py"
    for path, text in ((first, "NAME = 'first'\n"), (second, "NAME = 'second'\n")):
        path.parent.mkdir()
        path.write_text(text, encoding="utf-8")
    a, b = load_policy(first), load_policy(second)
    assert (a.NAME, b.NAME) == ("first", "second")
    assert load_policy(first) is a
    assert sys.modules[a.__name__] is a and sys.modules[b.__name__] is b and a.__name__ != b.__name__


@pytest.mark.parametrize("directory", [False, True], ids=["missing", "directory"])
def test_a_declared_policy_must_be_a_file(tmp_path, directory):
    path = tmp_path / "missing.py"
    if directory:
        path.mkdir()
    with pytest.raises(TargetSourceError, match="policy .* is not a file") as error:
        source.load_policies([str(path)])
    assert str(path) in str(error.value)


def test_explicit_policies_load_in_order_relative_to_the_invocation_cwd_or_absolute(tmp_path, monkeypatch):
    cwd, target_dir = tmp_path / "cwd", tmp_path / "targets"
    cwd.mkdir()
    target_dir.mkdir()
    monkeypatch.chdir(cwd)
    first = cwd / "rules.py"
    second = target_dir / "other.py"
    write(first, "NAME = 'cwd'\n")
    write(second, "NAME = 'absolute'\n")
    write(target_dir / "rules.py", "raise AssertionError('resolved against target directory')\n")
    modules = source.load_policies(["rules.py", str(second)])
    assert [module.NAME for module in modules] == ["cwd", "absolute"]
    assert list(source.load_policies(["rules.py", str(second)])) == list(modules)


def test_an_empty_policy_list_loads_nothing():
    assert list(source.load_policies([])) == []


def test_bazel_run_policies_use_the_invocation_directory(tmp_path, monkeypatch):
    invocation, runfiles = tmp_path / "invocation", tmp_path / "runfiles"
    invocation.mkdir()
    runfiles.mkdir()
    write(invocation / "rules.py", "NAME = 'invocation'\n")
    write(runfiles / "rules.py", "raise AssertionError('used runfiles cwd')\n")
    monkeypatch.chdir(runfiles)
    monkeypatch.setenv("BUILD_WORKING_DIRECTORY", str(invocation))
    assert source.load_policies(["./rules.py"])[0].NAME == "invocation"


def test_distinct_policies_cannot_publish_the_same_label(tmp_path):
    for name in ("first", "second"):
        write(
            tmp_path / f"{name}.py",
            "from score.itf import capability\n"
            "@capability('example.store', label='same')\n"
            "def make_store():\n    return object()\n",
        )
    with pytest.raises(ValueError, match="two capability factories are local.same"):
        Session(target={"policies": [str(tmp_path / "first.py"), str(tmp_path / "second.py")]}).resolve()


def test_session_reports_a_missing_declared_policy(tmp_path):
    missing = tmp_path / "missing.py"
    target = write(tmp_path / "target.yaml", f"policies: [{str(missing)!r}]\ncapabilities: {{}}\n")
    with pytest.raises(TargetSourceError, match="policy .* is not a file") as error:
        Session(target=target).resolve()
    assert str(missing) in str(error.value)


@pytest.mark.parametrize("clear", [False, True], ids=["include-adds", "override-clears"])
def test_session_loads_only_the_merged_target_policy_list(tmp_path, monkeypatch, clear):
    monkeypatch.chdir(tmp_path)
    marker = tmp_path / "loaded"
    for name in ("base", "extra"):
        write(
            tmp_path / f"{name}.py",
            f"from pathlib import Path\nwith Path({str(marker)!r}).open('a') as output:\n"
            f"    output.write({name!r} + '\\n')\n",
        )
    write(tmp_path / "base.yaml", "policies: [base.py]\ncapabilities: {}\n")
    target = write(tmp_path / "target.yaml", "include: [base.yaml]\npolicies: [extra.py]\n")
    overrides = [write(tmp_path / "clear.yaml", "policies: []\n")] if clear else []
    Session(target=target, overrides=overrides).resolve()
    if clear:
        assert not marker.exists()
    else:
        assert marker.read_text().splitlines() == ["base", "extra"]


def test_one_reader_for_a_file_or_inline_text(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    assert read_document(str(path)) == ("a: 1\n", path.resolve())
    assert read_document("b: 2\n") == ("b: 2\n", None)
    assert source.read_document(path)[1] == path.resolve()
