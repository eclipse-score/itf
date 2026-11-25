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
"""`@capability` and `@state`: slots, settings, labels, errors."""

import importlib
import sys
from dataclasses import dataclass
from typing import Protocol

import pytest

from score.itf.core import DuplicateLabel, capability, state
from score.itf.core.engine import registry
from score.itf.core.engine.metadata import contributor_metadata
from score.itf.core.engine.publish import declared_expectations, declared_parts, part_of, publish


class Shell(Protocol):
    __contract__ = "exec.shell"

    def run(self, command: str) -> str: ...


class Versioned(Protocol):
    __contract__ = "exec.shell@2"

    def run(self, command: str) -> str: ...


class NoContract(Protocol):
    def run(self, command: str) -> str: ...


@dataclass
class Settings:
    port: int = 22


class Exec:
    def exec(self, command): ...


def test_a_capability_factory_has_a_label_from_its_function_name():
    @capability("exec.command")
    def run_it(shell: Shell) -> Exec: ...

    descriptor = part_of(run_it)
    assert descriptor.pack == "local"
    assert descriptor.contract == "exec.command"
    assert run_it.__itf_label__ == "local.run_it"


def test_label_overrides_the_function_name():
    @capability("exec.command", label="exec")
    def make(shell: Shell) -> Exec: ...

    assert part_of(make).impl.endswith(".make")


def test_a_slot_takes_its_contract_and_shape_from_its_annotation():
    @capability("exec.command", label="slotted")
    def make(shell: Shell) -> Exec: ...

    (need,) = part_of(make).needs
    assert (need.slot, need.contract) == ("shell", "exec.shell")
    assert {m.name for m in need.expected.members} == {"run"}  # `__contract__` is not a member


def test_the_published_shape_is_the_return_annotation():
    @capability("exec.command", label="shaped")
    def make() -> Exec: ...

    assert {m.name for m in part_of(make).gives.members} == {"exec"}


def test_a_policy_only_contributor_publishes_strict_expectations(tmp_path, monkeypatch):
    module = _import(
        tmp_path,
        monkeypatch,
        "infra_only",
        """
from typing import Protocol
class Console(Protocol):
    __contract__ = "exec.console@1"
    def wait_for(self, pattern: str, *, regex: bool = False) -> str: ...
itf_expect = [Console]
""",
    )
    try:
        assert registry.is_contributor(module)
        catalog = publish(registry.register_modules(registry.follow([(module, "plugin")])))
        (expectation,) = catalog.expectations
        assert expectation.contract == "exec.console@1"
        assert expectation.origin == "infra_only"
        (member,) = expectation.shape.members
        assert member.name == "wait_for" and member.parameters is not None
        assert not catalog.factories and not catalog.actions
    finally:
        sys.modules.pop("infra_only", None)


@pytest.mark.parametrize("declaration", [None, "exec.console", [Shell, object], [NoContract]])
def test_invalid_policy_expectations_are_rejected(declaration):
    from types import ModuleType

    module = ModuleType("bad_infra")
    module.itf_expect = declaration
    with pytest.raises(TypeError, match="bad_infra.itf_expect"):
        declared_expectations(module)


def test_a_generator_factory_publishes_what_it_yields():
    from collections.abc import Iterator

    @capability("exec.command", label="yielding")
    def make() -> Iterator[Exec]:
        yield Exec()

    assert {m.name for m in part_of(make).gives.members} == {"exec"}


def test_a_dataclass_named_config_is_the_settings_schema():
    @capability("exec.command", label="configured")
    def make(config: Settings) -> Exec: ...

    schema = part_of(make).config_schema
    assert [f.name for f in schema.fields] == ["port"]
    assert schema.validate({"port": "x"}) and not schema.validate({"port": 2})


def test_major_is_split_from_the_contract_and_from_a_slot():
    @capability("exec.command@1", label="majored")
    def make(shell: Versioned) -> Exec: ...

    descriptor = part_of(make)
    assert (descriptor.contract, descriptor.major) == ("exec.command", 1)
    assert descriptor.need_majors == {"shell": 2}


def test_an_unannotated_parameter_is_an_error_naming_it():
    with pytest.raises(TypeError) as error:

        @capability("exec.command", label="bad")
        def make(shell): ...

    assert "'shell'" in str(error.value) and "__contract__" in str(error.value)


def test_an_annotation_without_a_contract_is_an_error_naming_the_parameter():
    with pytest.raises(TypeError, match="'shell'"):

        @capability("exec.command", label="bad")
        def make(shell: NoContract): ...


def test_config_must_be_a_dataclass():
    with pytest.raises(TypeError, match="'config'.*dataclass"):

        @capability("exec.command", label="bad")
        def make(config: dict): ...


def test_an_action_has_slots_after_breaks_and_also():
    @state("shell.open", after=("platform.up",), breaks=("shell.closed",), also=("network.reachable",), label="open")
    def open_it(shell: Shell) -> None: ...

    descriptor = part_of(open_it)
    assert (descriptor.state, descriptor.after, descriptor.breaks, descriptor.also) == (
        "shell.open",
        ("platform.up",),
        ("shell.closed",),
        ("network.reachable",),
    )
    assert [n.slot for n in descriptor.uses] == ["shell"]


def test_state_versions_are_preserved_in_every_delivered_and_required_token():
    @state("shell.open@2", after=("platform.up@1",), breaks=("shell.open@1",), also=("network.reachable@2",))
    def open_versioned(shell: Shell) -> None: ...

    descriptor = part_of(open_versioned)
    assert descriptor.state == "shell.open@2"
    assert descriptor.after == ("platform.up@1",)
    assert descriptor.breaks == ("shell.open@1",)
    assert descriptor.also == ("network.reachable@2",)


def test_a_state_list_given_as_a_string_is_an_error():
    with pytest.raises(TypeError, match="tuple"):

        @state("shell.open", after="platform.up")
        def open_it(): ...


def test_a_probe_takes_the_actions_slots():
    @state("shell.open", label="probed")
    def open_it(shell: Shell) -> None: ...

    @open_it.probe
    def is_open(shell: Shell) -> bool: ...

    assert part_of(open_it).probe.endswith("is_open")
    with pytest.raises(TypeError, match="probe"):

        @open_it.probe
        def wrong(other: Shell) -> bool: ...


def test_probe_for_names_a_state_the_action_also_makes():
    @state("shell.open", also=("network.reachable",), label="two")
    def open_it(shell: Shell) -> None: ...

    @open_it.probe_for("network.reachable")
    def reachable(shell: Shell) -> bool: ...

    assert part_of(open_it).extra_probes == {"network.reachable": reachable.__module__ + ":" + reachable.__qualname__}
    with pytest.raises(TypeError, match="also"):
        open_it.probe_for("other.state")


def _import(tmp_path, monkeypatch, name, text):
    (tmp_path / f"{name}.py").write_text(text, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return importlib.import_module(name)


def test_the_same_label_twice_in_a_module_is_an_error_when_published(tmp_path, monkeypatch):
    module = _import(
        tmp_path,
        monkeypatch,
        "twice_in_one",
        "from score.itf.core import capability\n\n"
        "@capability('x.y', label='twice')\ndef first(): ...\n\n"
        "@capability('x.y', label='twice')\ndef second(): ...\n",
    )
    try:
        with pytest.raises(DuplicateLabel, match="local.twice"):
            publish(registry.register_modules([(module, "policy")]))
    finally:
        sys.modules.pop("twice_in_one", None)


def test_publishing_twice_or_after_a_reload_never_sees_stale_or_duplicate_parts(tmp_path, monkeypatch):
    head = "from score.itf.core import capability\n\n"
    module = _import(tmp_path, monkeypatch, "reloaded", head + "@capability('x.y', label='old')\ndef make(): ...\n")
    try:
        first = publish(registry.register_modules([(module, "policy")]))
        again = publish(registry.register_modules([(module, "policy")]))  # another session, same module
        assert set(first.factories) == set(again.factories) == {"local.old"}
        (tmp_path / "reloaded.py").write_text(
            head + "@capability('x.y', label='brand_new_one')\ndef make(): ...\n", encoding="utf-8"
        )
        importlib.invalidate_caches()
        reloaded = publish(registry.register_modules([(importlib.reload(module), "policy")]))
        assert set(reloaded.factories) == {"local.brand_new_one"}
    finally:
        sys.modules.pop("reloaded", None)


def test_a_function_imported_into_another_module_is_published_by_the_module_that_defines_it(tmp_path, monkeypatch):
    head = "from score.itf.core import capability\n\n"
    home = _import(tmp_path, monkeypatch, "home_of_part", head + "@capability('x.y', label='one')\ndef make(): ...\n")
    other = _import(tmp_path, monkeypatch, "importer", "from home_of_part import make\n")
    try:
        published = publish(registry.register_modules([(home, "policy")]))
        assert set(published.factories) == {"local.one"}
        assert declared_parts(other) == []
    finally:
        for name in ("home_of_part", "importer"):
            sys.modules.pop(name, None)


def test_the_pack_metadata_is_not_looked_for_above_the_package_root(tmp_path, monkeypatch):
    (tmp_path / "pack.yaml").write_text("name: stray\nversion: 1\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "plain.py").write_text("", encoding="utf-8")
    pack = tmp_path / "realpack"
    (pack / "sub").mkdir(parents=True)
    for init in (pack / "__init__.py", pack / "sub" / "__init__.py"):
        init.write_text("", encoding="utf-8")
    (pack / "pack.yaml").write_text("name: real\nversion: 1\n", encoding="utf-8")
    (pack / "sub" / "deep.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(project))
    monkeypatch.syspath_prepend(str(tmp_path))
    import plain
    import realpack.sub.deep as deep

    try:
        assert contributor_metadata(plain) is None  # `project` has no __init__.py: the walk stops there
        assert contributor_metadata(deep) == {"name": "real", "version": 1}  # inside a package it climbs
    finally:
        for name in [n for n in sys.modules if n.split(".")[0] in ("plain", "realpack")]:
            del sys.modules[name]


def test_the_same_label_in_two_modules_is_an_error_when_published(tmp_path, monkeypatch):
    for name in ("dup_one", "dup_two"):
        (tmp_path / f"{name}.py").write_text(
            "from score.itf.core import capability\n\n@capability('x.y', label='clash')\ndef make(): ...\n",
            encoding="utf-8",
        )
    monkeypatch.syspath_prepend(str(tmp_path))
    import dup_one
    import dup_two

    try:
        reg = registry.register_modules([(dup_one, "policy"), (dup_two, "policy")])
        with pytest.raises(DuplicateLabel, match="local.clash"):
            publish(reg)
    finally:
        for name in ("dup_one", "dup_two"):
            sys.modules.pop(name, None)


def test_the_pack_is_the_pack_yaml_name_above_the_module(tmp_path, monkeypatch):
    package = tmp_path / "mypack_dir"
    package.mkdir()
    (package / "pack.yaml").write_text("name: acme\nversion: 1\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "parts.py").write_text(
        "from score.itf.core import capability, state\n\n"
        "@capability('x.y')\ndef thing(): ...\n\n"
        "@state('x.up', label='go')\ndef go(): ...\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    import mypack_dir.parts as parts

    try:
        assert parts.thing.__itf_label__ == "acme.thing"
        assert parts.go.__itf_label__ == "acme.go"
    finally:
        for name in [n for n in sys.modules if n.startswith("mypack_dir")]:
            del sys.modules[name]


def test_no_pack_may_be_named_local_the_projects_policy_owns_that_prefix():
    from score.itf.core.engine.metadata import pack_name

    with pytest.raises(ValueError, match="reserved for the project's policy"):
        pack_name({"name": "local", "version": 1})
