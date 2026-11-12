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
from unittest.mock import Mock

import pytest

from score.itf.packs.ping import ping as legacy


@pytest.mark.parametrize("helper,lost", [(legacy.ping, False), (legacy.ping_lost, True)])
def test_immediate_probe_does_not_sleep(monkeypatch, helper, lost):
    probe = Mock(return_value=not lost)
    sleep = Mock()
    monkeypatch.setattr(legacy, "_ping", probe)
    monkeypatch.setattr(legacy.time, "sleep", sleep)
    assert helper("ecu", wait_ms_precision=0.2)
    probe.assert_called_once_with("ecu", 0.2)
    sleep.assert_not_called()


@pytest.mark.parametrize("helper,answers", [(legacy.ping, [False, True]), (legacy.ping_lost, [True, False])])
def test_wait_sleeps_before_each_attempt(monkeypatch, helper, answers):
    events = []
    monkeypatch.setattr(legacy.time, "sleep", lambda interval: events.append(interval))
    monkeypatch.setattr(legacy, "_ping", lambda *args: events.append("probe") or answers.pop(0))
    assert helper("ecu", 5, 2, 0.1)
    assert events == [2, "probe", 2, "probe"]


@pytest.mark.parametrize("helper,answer", [(legacy.ping, False), (legacy.ping_lost, True)])
def test_wait_truncates_attempts_and_exhausts(monkeypatch, helper, answer):
    probe = Mock(return_value=answer)
    monkeypatch.setattr(legacy, "_ping", probe)
    monkeypatch.setattr(legacy.time, "sleep", Mock())
    assert not helper("ecu", 2.9)
    assert probe.call_count == 2
    probe.reset_mock()
    assert not helper("ecu", 0.5)
    probe.assert_not_called()


@pytest.mark.parametrize("precision,prefix", [(None, ""), (0, ""), (0.2, "timeout 0.2 ")])
def test_original_binary_command(monkeypatch, precision, prefix):
    monkeypatch.setattr(legacy.shutil, "which", lambda name: "/fake/ping")
    execute = Mock(return_value=0)
    monkeypatch.setattr(legacy, "_execute_command", execute)
    assert legacy._ping("192.0.2.1", precision)
    execute.assert_called_once_with(prefix + "ping -c 1 -W 1 192.0.2.1")
    execute.return_value = 1
    assert not legacy._ping("192.0.2.1", precision)


def test_missing_binary_and_assertion_helpers(monkeypatch):
    monkeypatch.setattr(legacy.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="utility is not installed"):
        legacy.ping("ecu")
    for name in ("ping", "ping_lost"):
        probe = Mock(return_value=True)
        monkeypatch.setattr(legacy, name, probe)
        assert getattr(legacy, "check_" + name)("ecu") is None
        probe.assert_called_once_with("ecu", timeout=60)
        probe.return_value = False
        with pytest.raises(AssertionError):
            getattr(legacy, "check_" + name)("ecu")


def test_canonical_factory_binds_the_ping_api_to_one_endpoint(monkeypatch):
    from types import SimpleNamespace
    from score.itf.packs.ping.providers import make_ping

    probe = Mock(return_value=True)
    monkeypatch.setattr(legacy, "_ping", probe)
    node = make_ping(SimpleNamespace(host="ecu"))
    assert isinstance(node, legacy.Ping)
    assert node.ping(wait_ms_precision=0.2)
    probe.assert_called_once_with("ecu", 0.2)
    assert not node.ping_lost()


def test_icmp_provider_keeps_the_canonical_ping_api(monkeypatch):
    from types import SimpleNamespace
    from score.itf.packs.ping.icmp import probe as icmp
    from score.itf.packs.ping.providers import make_pinger

    probe = Mock(return_value=True)
    monkeypatch.setattr(icmp, "ping", probe)
    node = make_pinger(SimpleNamespace(host="ecu"), {})
    assert isinstance(node, legacy.Ping)
    assert node.ping(wait_ms_precision=0.2)
    probe.assert_called_once_with("ecu", 0.2, "ping")
    assert not node.ping_lost()


def test_one_shot_icmp_signature_and_backend_are_unchanged(monkeypatch):
    import inspect
    from unittest.mock import MagicMock
    from score.itf.packs.ping.icmp import probe as icmp

    assert (
        str(inspect.signature(icmp.ping)) == "(host: 'str', timeout: 'float' = 1.0, binary: 'str' = 'ping') -> 'bool'"
    )
    monkeypatch.setattr(icmp.socket, "gethostbyname", lambda host: "192.0.2.1")
    sock = MagicMock()
    monkeypatch.setattr(icmp, "_open_socket", lambda: (sock, False))
    echo = Mock(return_value=True)
    monkeypatch.setattr(icmp, "_ping_socket", echo)
    assert icmp.ping("ecu", 0.2, "custom-ping")
    echo.assert_called_once_with(sock, False, "192.0.2.1", 0.2)
    sock.__exit__.assert_called_once_with(None, None, None)
    monkeypatch.setattr(icmp, "_open_socket", lambda: None)
    monkeypatch.setattr(icmp.shutil, "which", lambda binary: "/fake/ping")
    run = Mock(return_value=(0, "", ""))
    monkeypatch.setattr(icmp.ProcessWrapper, "run", run)
    assert icmp.ping("ecu", 1, "custom-ping")
    run.assert_called_once_with("custom-ping", ["-c", "1", "-W", "1", "192.0.2.1"], timeout=3)
