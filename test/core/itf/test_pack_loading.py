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
"""Packs load from the labels of a target file: the module `score.itf.packs.<name>.plugin`, else an entry point."""

import importlib.metadata
import sys

import pytest

from score.itf.core import PackNotFound, Session
from score.itf.core.engine import packs as pack_loader


def test_a_pack_is_the_plugin_module_under_score_itf_packs():
    assert pack_loader.load("localhost").__name__ == "score.itf.packs.localhost.plugin"
    assert pack_loader.pack_of("localhost.exec") == "localhost"


def test_an_unknown_pack_is_a_clear_error_listing_what_is_known():
    with pytest.raises(PackNotFound) as error:
        pack_loader.load("nope")
    text = str(error.value)
    assert "score.itf.packs.nope.plugin" in text and "score_itf.packs" in text and "local" in text


def test_the_target_file_alone_loads_its_packs(tmp_path):
    session = Session(
        target="capabilities:\n  platform: localhost.platform\n  command: localhost.exec\ngoals:\n  - platform.up\n",
        plan_only=True,
        run_dir=tmp_path / "run",
    ).resolve()
    assert {"localhost.platform", "localhost.exec", "localhost.start"} <= set(session.catalog.factories) | set(
        session.catalog.action_descs
    )
    assert session.catalog.packs() == ("localhost",)  # a pack that is not named is not loaded
    assert [n.provider for n in session.target_plan.nodes] == ["localhost.exec", "localhost.platform"]
    assert [s.delivers for s in session.action_plan.steps] == [("__itf_root__:platform.up",)]


def test_the_loaded_packs_are_logged_with_their_version(tmp_path, caplog):
    caplog.set_level("INFO", logger="score.itf.core")
    Session(
        target="capabilities:\n  platform: localhost.platform\n", plan_only=True, run_dir=tmp_path / "run"
    ).resolve()
    assert "pack localhost 0.1.0 (score.itf.packs.localhost.plugin)" in caplog.text


def test_a_label_of_an_unknown_pack_is_an_error_naming_the_pack(tmp_path):
    with pytest.raises(PackNotFound, match="'acme'"):
        Session(target="capabilities:\n  x: acme.thing\n", plan_only=True, run_dir=tmp_path / "run").resolve()


def test_an_entry_point_pack_loads_when_no_such_module_exists(tmp_path, monkeypatch):
    pack = tmp_path / "vendorx"
    pack.mkdir()
    (pack / "pack.yaml").write_text("name: vendorx\nversion: 1\n", encoding="utf-8")
    (pack / "__init__.py").write_text("", encoding="utf-8")
    (pack / "plugin.py").write_text('pytest_plugins = ["vendorx.parts"]\n', encoding="utf-8")
    (pack / "parts.py").write_text(
        "from score.itf.core import capability\n\n@capability('x.thing')\ndef thing() -> object: ...\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    entry = importlib.metadata.EntryPoint(name="vendorx", value="vendorx.plugin", group="score_itf.packs")
    real = importlib.metadata.entry_points
    monkeypatch.setattr(
        importlib.metadata, "entry_points", lambda **kw: [entry] if kw.get("group") == "score_itf.packs" else real(**kw)
    )
    try:
        session = Session(target="capabilities:\n  t: vendorx.thing\n", plan_only=True, run_dir=tmp_path / "run")
        session.resolve()
        assert [n.provider for n in session.target_plan.nodes] == ["vendorx.thing"]
        assert "vendorx" in pack_loader.known()
    finally:
        for name in [n for n in sys.modules if n.startswith("vendorx")]:
            del sys.modules[name]


def test_project_labels_load_no_pack(tmp_path):
    import kv_parts

    session = Session([kv_parts], target="capabilities:\n  s: local.store\n", plan_only=True, run_dir=tmp_path / "run")
    session.resolve()
    assert session.catalog.packs() == ("local",)
