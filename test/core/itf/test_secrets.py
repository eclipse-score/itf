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
"""ITF never shows a secret: a sensitive setting's value is masked in every log record while a session runs, in
failure reports and evidence, and in pytest's failure output."""

import json
import logging

import pytest
import secret_parts
import vault_parts

from score.itf.core import NotReady, Session
from score.itf.core.engine.secrets import Secrets

VAULT = "capabilities:\n  vault:\n    factory: local.vault\n    with:\n      user: bob\n      password: swordfish-42\n"
TOKEN = (
    "capabilities:\n  token:\n    factory: local.token\n    with:\n      value: tok-123456\ngoals:\n  - kv.logged_in\n"
)


class Kept(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


@pytest.fixture
def kept():
    handler, log = Kept(), logging.getLogger("anywhere")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    yield log, handler.messages
    log.removeHandler(handler)


def test_values_too_short_to_mask_safely_are_left_alone():
    secrets = Secrets()
    secrets.add("score")
    secrets.add("long-enough")
    assert secrets.mask("score: long-enough") == "score: [redacted]"


def test_a_sensitive_setting_is_masked_in_any_log_record_while_the_session_runs(tmp_path, kept):
    log, messages = kept
    session = Session([vault_parts], target=VAULT, plan_only=True, run_dir=tmp_path / "run").resolve()
    log.info("connecting with %s", "swordfish-42")
    session.close()
    log.info("after the session: swordfish-42")
    assert messages == ["connecting with [redacted]", "after the session: swordfish-42"]


def test_every_setting_of_a_sensitive_capability_is_a_secret(tmp_path, kept):
    log, messages = kept
    session = Session([secret_parts], target=TOKEN, run_dir=tmp_path / "run", artifacts="full").resolve()
    log.info("token tok-123456")
    with pytest.raises(NotReady) as failed:
        session.bring_up()
    session.close()
    assert messages == ["token [redacted]"]
    assert "tok-123456" not in str(failed.value) and "[redacted]" in str(failed.value)
    for name in ("plan.json", "claims.json", "evidence.json"):
        assert "tok-123456" not in (tmp_path / "run" / name).read_text(), name
    plan = json.loads((tmp_path / "run" / "plan.json").read_text())
    assert plan["target"]["nodes"][0]["config"] == {"value": "[redacted]"}


def test_a_secret_containing_another_is_masked_whole_across_sessions():
    one, two = Secrets(), Secrets()
    one.add("hunter2")
    two.add("hunter2-secret")
    one.install()
    two.install()
    try:
        from score.itf.core.engine.secrets import mask

        assert mask("pw hunter2-secret and hunter2") == "pw [redacted] and [redacted]"
    finally:
        two.uninstall()
        one.uninstall()
