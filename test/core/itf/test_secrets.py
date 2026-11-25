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
"""ITF redacts marked configuration in its own plans without rewriting component output."""

import json
import logging

import pytest
import secret_parts
import vault_parts

from score.itf.core import Session
from score.itf.core.engine.secrets import Secrets
from score.itf.core.frontends.target_file import TargetFileError
from score.itf.core.frontends.target_source import TargetSource

VAULT = "capabilities:\n  vault:\n    factory: local.vault\n    with:\n      user: bob\n      password: swordfish-42\n"


class Kept(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def test_marked_config_is_redacted_in_itf_artifacts_but_kept_typed_at_runtime(tmp_path):
    run_dir = tmp_path / "run"
    session = Session([vault_parts], target=VAULT, plan_only=True, run_dir=run_dir, artifacts="full").resolve()
    try:
        node = session.target_plan.nodes[0]
        assert dict(node.config)["password"] == "swordfish-42"
        assert session.target.vault.config["password"] == "swordfish-42"

        plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
        claims = json.loads((run_dir / "claims.json").read_text(encoding="utf-8"))
        assert plan["target"]["nodes"][0]["config"]["password"] == "[redacted]"
        assert "swordfish-42" not in json.dumps(claims)
        assert "swordfish-42" not in (run_dir / "target.html").read_text(encoding="utf-8")
    finally:
        session.close()


def test_short_sensitive_setting_is_redacted_without_masking_other_config(tmp_path):
    target = (
        "capabilities:\n  token:\n    factory: local.token\n    with:\n"
        "      value: xy\n      label: public-label\ngoals:\n  - kv.logged_in\n"
    )
    run_dir = tmp_path / "run"
    session = Session([secret_parts], target=target, plan_only=True, run_dir=run_dir, artifacts="full").resolve()
    try:
        config = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))["target"]["nodes"][0]["config"]
        assert config == {"label": "public-label", "value": "[redacted]"}
        assert session.target.token.value == "xy"
    finally:
        session.close()


def test_secret_registry_does_not_rewrite_arbitrary_log_records():
    handler = Kept()
    core_log = logging.getLogger("score.itf.core")
    component_log = logging.getLogger("score.itf.packs.vault")
    core_log.addHandler(handler)
    component_log.addHandler(handler)
    previous_levels = core_log.level, component_log.level
    core_log.setLevel(logging.WARNING)
    component_log.setLevel(logging.WARNING)
    secrets = Secrets()
    secrets.add("swordfish-42")
    assert secrets.mask("ITF diagnostic: swordfish-42") == "ITF diagnostic: [redacted]"
    session = Session()
    session.secrets.add("swordfish-42")
    try:
        core_log.warning("ITF diagnostic: %s", "swordfish-42")
        component_log.warning("component output: %s", "swordfish-42")
        session._log_event(
            "action_finished", {"step": "vault.open", "ok": False, "error": "provider error: swordfish-42"}
        )
        assert handler.messages[:2] == [
            "ITF diagnostic: swordfish-42",
            "component output: swordfish-42",
        ]
        assert "vault.open: failed" in handler.messages[2]
        assert "provider error: [redacted]" in handler.messages[2]
        assert "swordfish-42" not in handler.messages[2]
    finally:
        core_log.removeHandler(handler)
        component_log.removeHandler(handler)
        core_log.setLevel(previous_levels[0])
        component_log.setLevel(previous_levels[1])


def test_malformed_yaml_error_does_not_echo_input_secret():
    secret = "parser-secret-9081"
    target = f"capabilities: [\n  vault:\n    password: {secret}\n"
    with pytest.raises(TargetFileError) as error:
        Session([vault_parts], target=TargetSource(target, "inline-test"), plan_only=True).resolve()
    assert secret not in str(error.value)


def test_session_text_redactor_ignores_short_values_to_avoid_false_positives():
    secrets = Secrets()
    secrets.add("xy")
    secrets.add("long-enough-secret")
    assert secrets.mask("xy long-enough-secret") == "xy [redacted]"


def test_structured_text_redaction_touches_only_report_text_fields():
    secrets = Secrets()
    secrets.add("swordfish-42")
    value = {
        "message": "swordfish-42",
        "steps": [{"error": "failed: swordfish-42", "name": "swordfish-42"}],
    }
    assert secrets.mask_text_fields(value) == {
        "message": "swordfish-42",
        "steps": [{"error": "failed: [redacted]", "name": "swordfish-42"}],
    }
