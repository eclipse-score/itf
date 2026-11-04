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
import logging
import os
import sys
from inspect import signature
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from score.itf.core.process import ProcessWrapper
from score.itf.packs.dlt.receive.process import DltReceive, Protocol
from score.itf.packs.dlt.receive.window import Bunch, DltLogRecord, DltWindow, _normalize_timestamp_precision
from score.itf.packs.dlt.receive import capture as tool


def test_protocol_is_shared_and_receive_is_a_process(tmp_path, monkeypatch):
    assert Protocol is tool.Transport
    output = tmp_path / "receive.dlt"
    output.write_text("old")
    receiver = DltReceive(
        Protocol.UDP, "192.0.2.1", ["239.1.1.1"], file_name=str(output), print_to_stdout=True, binary_path="fake"
    )
    assert isinstance(receiver, ProcessWrapper)
    assert receiver.file_name() == str(output)
    assert not output.exists()
    assert receiver._args == [
        "-o",
        str(output),
        "--udp",
        "--net-if",
        "192.0.2.1",
        "--port",
        "3490",
        "--mcast-ip",
        "239.1.1.1",
        "-a",
    ]
    start, stop = Mock(), Mock()
    monkeypatch.setattr(receiver, "start_process", start)
    monkeypatch.setattr(receiver, "kill_process", stop)
    with receiver as handle:
        assert handle is receiver
    start.assert_called_once_with(receiver._args)
    stop.assert_called_once_with()


def test_stdout_only_receiver_retains_existing_file(tmp_path):
    output = tmp_path / "receive.dlt"
    output.write_text("old")
    receiver = DltReceive(
        Protocol.TCP, target_ip="192.0.2.2", file_name=str(output), enable_file_output=False, binary_path="fake"
    )
    assert receiver._args == ["--tcp", "192.0.2.2"]
    assert output.read_text() == "old"


def test_window_context_filter_capture_and_cleanup(tmp_path, monkeypatch):
    output = tmp_path / "window.dlt"
    output.write_text("retain")
    window = DltWindow(
        Protocol.TCP,
        target_ip="192.0.2.2",
        file_name=str(output),
        print_to_stdout=True,
        logger_name="fake.dlt.window",
        dlt_filter="APP CTX",
        binary_path="fake",
    )
    assert output.read_text() == "retain"
    assert window._args == ["-o", str(output), "--tcp", "192.0.2.2", "-a", "--stdout-flush", "-f", window._filter_file]
    with open(window._filter_file) as filter_file:
        assert filter_file.read() == "APP CTX\n\n"
    start, stop = Mock(), Mock()
    monkeypatch.setattr(window, "start_process", start)
    monkeypatch.setattr(window, "kill_process", stop)
    captured = window.get_captured_logs()
    with pytest.raises(ValueError, match="test body"):
        with window as handle:
            assert handle is window
            logging.getLogger("fake.dlt.window").info("received")
            assert "fake.dlt.window - INFO - received" in window.get_logged_output()
            assert window.get_captured_logs() is captured
            assert window.get_logged_output(True)
            assert captured == []
            logging.getLogger("fake.dlt.window").info("again")
            raise ValueError("test body")
    start.assert_called_once_with(window._args)
    stop.assert_called_once_with()
    assert captured == []
    assert window._log_handler not in window._logger.handlers
    assert not os.path.exists(window._filter_file)
    assert output.exists()


def _fake_dlt(monkeypatch, messages):
    class Content(list):
        counter_total = 7
        counter = 3

    load = Mock(return_value=Content(messages))
    package = ModuleType("dlt")
    module = ModuleType("dlt.dlt")
    module.load = load
    package.dlt = module
    monkeypatch.setitem(sys.modules, "dlt", package)
    monkeypatch.setitem(sys.modules, "dlt.dlt", module)
    return load


def _message(extended=True, matches=True):
    return SimpleNamespace(
        use_extended_header=extended,
        compare=Mock(return_value=matches),
        payload_decoded=b"hello\xff",
        tmsp=1.5,
        apid="APP",
        ctid="CTX",
        storage_timestamp=1700.12,
    )


def test_record_reuses_search_but_restores_original_results(monkeypatch):
    messages = [_message(False), _message(matches=False), _message()]
    load = _fake_dlt(monkeypatch, messages)
    record = DltLogRecord("fake.dlt", [("APP", "CTX")])
    load.assert_called_once_with("fake.dlt", filters=[("APP", "CTX")])
    result = record.find({"apid": "APP"})
    assert tool.DltLogRecord is DltLogRecord
    assert issubclass(tool.DltCaptureRecord, DltLogRecord)
    assert len(result) == 1 and isinstance(result[0], Bunch)
    assert vars(result[0]) == dict(
        time_stamp=1.5, apid="APP", ctid="CTX", payload="hello", raw_msg=messages[2], epoch_time="1700.000012"
    )
    assert (record.total_count(), record.filtered_count(), record.queried_count()) == (7, 3, 2)
    assert result[0].get("payload") == "hello"
    result[0].update(extra=1)
    assert result[0].extra == 1
    assert len(record.find(include_non_ext=True, full_match=False)) == 1
    assert record.queried_count() == 1
    assert record.find(include_ext=False, include_non_ext=False) == []
    assert record.queried_count() == 1
    assert tool.DltCaptureRecord("fake.dlt").find()[0].payload == b"hello\xff"


def test_timeout_and_window_record(monkeypatch, tmp_path):
    _fake_dlt(monkeypatch, [_message(), _message()])
    monkeypatch.setattr(DltLogRecord, "_clock", Mock(side_effect=[10, 11]))
    record = DltLogRecord("fake.dlt")
    assert len(record.find(timeout=0.5)) == 1
    assert record.queried_count() == 1
    window = DltWindow(Protocol.TCP, target_ip="ecu", file_name=str(tmp_path / "window"), binary_path="fake")
    assert isinstance(window.record(), DltLogRecord)
    monkeypatch.setattr(window, "kill_process", Mock())
    window.stop()


@pytest.mark.parametrize("timestamp,expected", [(1.2, "1.000002"), (1.123456, "1.123456"), ("1.1234567", "1.1234567")])
def test_original_timestamp_padding(timestamp, expected):
    assert _normalize_timestamp_precision(timestamp) == expected


def test_original_malformed_timestamp_error(caplog):
    with pytest.raises(UnboundLocalError):
        _normalize_timestamp_precision(1)
    assert "Error normalizing timestamp precision" in caplog.text


def _request(**options):
    return SimpleNamespace(config=SimpleNamespace(getoption=lambda name, default=None: options.get(name, default)))


def test_explicit_window_start_stop_and_default_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_UNDECLARED_OUTPUTS_DIR", str(tmp_path))
    receiver = DltReceive(Protocol.TCP, target_ip="ecu", binary_path="fake")
    assert receiver.file_name() == str(tmp_path / "dlt_receive.dlt")
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    window = DltWindow(Protocol.TCP, target_ip="ecu", binary_path="fake")
    assert os.path.isfile(window.file_name())
    start, stop = Mock(), Mock()
    monkeypatch.setattr(window, "start_process", start)
    monkeypatch.setattr(window, "kill_process", stop)
    assert window.start() is None
    assert window.stop() is None
    start.assert_called_once_with(window._args)
    stop.assert_called_once_with()


def test_original_constructor_and_search_defaults():
    receive = dict(
        protocol=Protocol.UDP,
        host_ip=None,
        multicast_ips=None,
        target_ip=None,
        file_name=None,
        enable_file_output=True,
        print_to_stdout=False,
        logger_name=None,
        binary_path=None,
    )
    window = dict(
        protocol=Protocol.UDP,
        host_ip=None,
        multicast_ips=None,
        target_ip=None,
        file_name=None,
        print_to_stdout=False,
        logger_name=None,
        dlt_filter=None,
        binary_path=None,
    )
    search = dict(query=None, include_ext=True, include_non_ext=False, full_match=True, timeout=None)
    for callable_api, defaults in ((DltReceive, receive), (DltWindow, window), (DltLogRecord.find, search)):
        parameters = {
            name: parameter.default for name, parameter in signature(callable_api).parameters.items() if name != "self"
        }
        assert list(parameters) == list(defaults)
        assert parameters == defaults


def test_capture_records_and_window_results_extend_canonical_records(monkeypatch, tmp_path):
    raw = _message()
    raw.ecuid = "ECU"
    _fake_dlt(monkeypatch, [raw])
    output = tmp_path / "capture.dlt"
    capture = tool.DltCapture({"file_name": str(output), "binary_path": "fake"})
    assert capture.lines() == []
    output.write_bytes(b"fixture")
    record = capture.record([("APP", "CTX")])
    assert isinstance(record, DltLogRecord)
    found = capture.lines()
    assert found[0].ecu_id == "ECU"
    assert found[0].payload == b"hello\xff"
    assert found[0].text() == "hello\ufffd"
    assert found[0].raw is raw
    assert capture.filter(apid="APP", ctid="CTX") == found
    assert capture.filter(apid="OTHER") == []
    monkeypatch.setattr(ProcessWrapper, "start_process", Mock())
    monkeypatch.setattr(ProcessWrapper, "kill_process", Mock())
    with capture.window() as window:
        assert isinstance(window, DltWindow)
        assert isinstance(window.record(), tool.DltCaptureRecord)
        with open(window.file_name(), "wb") as output:
            output.write(b"fixture")
        assert window.record().find() == found


def test_capture_lines_returns_empty_for_an_empty_file(tmp_path):
    output = tmp_path / "empty.dlt"
    capture = tool.DltCapture({"file_name": str(output), "binary_path": "fake"})
    output.touch()

    assert capture.lines() == []


def test_record_find_returns_empty_for_an_empty_file(tmp_path, monkeypatch):
    output = tmp_path / "empty.dlt"
    output.touch()
    _fake_dlt(monkeypatch, [])
    record = DltLogRecord(str(output))

    assert record.find() == []
    assert record.queried_count() == 0


def test_window_start_error_is_preserved_when_cleanup_fails(tmp_path, monkeypatch):
    window = DltWindow(
        Protocol.TCP,
        target_ip="ecu",
        file_name=str(tmp_path / "window"),
        dlt_filter="APP CTX",
        logger_name="fake.dlt.cleanup.failure",
        binary_path="fake",
    )
    monkeypatch.setattr(window, "start_process", Mock(side_effect=RuntimeError("start failure")))
    monkeypatch.setattr(os, "remove", Mock(side_effect=OSError("cleanup failure")))

    with pytest.raises(RuntimeError, match="start failure"):
        window.start()

    assert os.path.exists(window._filter_file)
    assert window._log_handler not in window._logger.handlers
    assert window.get_captured_logs() == []


def test_window_start_failure_cleans_filter_and_handler(tmp_path, monkeypatch):
    window = DltWindow(
        Protocol.TCP,
        target_ip="ecu",
        file_name=str(tmp_path / "window"),
        dlt_filter="APP CTX",
        logger_name="fake.dlt.failure",
        binary_path="fake",
    )
    monkeypatch.setattr(window, "start_process", Mock(side_effect=OSError("start failure")))
    stop = Mock()
    monkeypatch.setattr(window, "kill_process", stop)
    with pytest.raises(OSError, match="start failure"):
        window.start()
    stop.assert_not_called()
    assert not os.path.exists(window._filter_file)
    assert window._log_handler not in window._logger.handlers
