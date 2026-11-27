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
"""dlt-receive arguments: the node's transport, and a per-recording override (window())."""

import os
import socket
import subprocess
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from score.itf.core.process import ProcessWrapper
from score.itf.packs.dlt.receive.process import DltReceive, bundled
from score.itf.packs.dlt.receive.window import DltWindow
from score.itf.packs.dlt.receive.providers import make_receive, make_receive_tcp
from score.itf.packs.dlt.receive.capture import DltCapture, Transport

# First network frame from dlt-daemon's tests/testfile.dlt, without its storage header.
DLT_FRAME = bytes.fromhex(
    "35 00 00 1f 45 43 55 00 3f 88 62 3a 16 01 41 50 50 00 43 4f 4e 00 11 00 00 00 04 72 65 6d 6f"
)


def _udp():
    return DltCapture({"host_ip": "127.0.0.1", "multicast_ips": "224.0.0.1", "binary_path": "dlt-receive"})


def _tcp():
    return DltCapture({"binary_path": "dlt-receive"}, SimpleNamespace(host="10.0.0.5", port=13490))


def test_a_udp_node_joins_its_groups_on_its_interface():
    node = _udp()
    assert node._args == [
        "-o",
        node.path(),
        "--udp",
        "--net-if",
        "127.0.0.1",
        "--port",
        "3490",
        "--mcast-ip",
        "224.0.0.1",
    ]


def test_a_tcp_node_connects_to_its_endpoint():
    node = _tcp()
    assert node._args == ["-o", node.path(), "--tcp", "10.0.0.5"]


def test_tcp_receiver_reconnects_and_records_data_after_daemon_disconnect(tmp_path):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(7)
    port = listener.getsockname()[1]
    reconnected = threading.Event()
    accept_errors = []

    def accept_then_close():
        try:
            connection, _ = listener.accept()
            connection.close()
            connection, _ = listener.accept()
            connection.sendall(DLT_FRAME)
            connection.close()
            reconnected.set()
        except OSError as error:
            accept_errors.append(error)
        finally:
            listener.close()

    server = threading.Thread(target=accept_then_close, daemon=True)
    server.start()
    recording = tmp_path / "reconnected.dlt"
    receiver = subprocess.Popen(
        [bundled("dlt-receive"), "-o", str(recording), "--tcp", "127.0.0.1"],
        env={**os.environ, "DLT_DAEMON_TCP_PORT": str(port)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert reconnected.wait(timeout=7)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and (not recording.exists() or DLT_FRAME not in recording.read_bytes()):
            time.sleep(0.01)
        assert recording.is_file(), "dlt-receive did not create its recording after reconnect"
        assert DLT_FRAME in recording.read_bytes()
        assert receiver.poll() is None
        assert not accept_errors
    finally:
        receiver.terminate()
        try:
            receiver.wait(timeout=3)
        except subprocess.TimeoutExpired:
            receiver.kill()
            receiver.wait(timeout=3)
        listener.close()
        server.join(timeout=2)


@pytest.fixture
def fake_process(monkeypatch):
    start, stop = Mock(), Mock()
    monkeypatch.setattr(ProcessWrapper, "start_process", start)
    monkeypatch.setattr(ProcessWrapper, "kill_process", stop)
    monkeypatch.setattr(ProcessWrapper, "is_running", lambda self: True)
    return start, stop


def test_a_route_aims_one_recording_elsewhere_without_touching_the_node(fake_process):
    node = _udp()
    original = node._args.copy()
    with node.window(transport=Transport.TCP, target_ip="172.17.0.2", print_to_stdout=True) as window:
        assert isinstance(window, DltWindow)
        assert window._args == ["-o", window.file_name(), "--tcp", "172.17.0.2", "-a", "--stdout-flush"]
    with node.window(host_ip="172.17.0.1", multicast_ips=["239.1.1.1"]) as window:
        assert window._args[-4:] == ["--port", "3490", "--mcast-ip", "239.1.1.1"]
        assert "172.17.0.1" in window._args
    with node.window(multicast_ips=[]) as window:
        assert "--mcast-ip" not in window._args
    assert node._args == original
    start, stop = fake_process
    assert start.call_count == stop.call_count == 3
    assert not node.is_active()


def test_capture_reuses_canonical_process_and_is_inert_until_subscribed(tmp_path, fake_process):
    output = tmp_path / "capture.dlt"
    output.write_text("previous")
    capture = DltCapture({"file_name": str(output), "print_to_stdout": True, "binary_path": "fake"})
    assert isinstance(capture, DltReceive)
    assert capture.file_name() == capture.path() == str(output)
    assert capture._args[-2:] == ["-a", "--stdout-flush"]
    assert output.read_text() == "previous"
    assert not capture.is_active()
    start, stop = fake_process
    capture.close()
    stop.assert_not_called()
    capture.subscribe()
    assert not output.exists()
    assert capture.is_active()
    capture.subscribe()
    start.assert_called_once_with(capture._args)
    capture.close()
    capture.close()
    stop.assert_called_once_with()
    assert not capture.is_active()
    capture.subscribe()
    capture.close()
    assert start.call_count == stop.call_count == 2


def test_capture_creates_output_directory_at_subscription(tmp_path, fake_process):
    output = tmp_path / "nested" / "capture.dlt"
    capture = DltCapture({"file_name": str(output), "binary_path": "fake"})
    assert not output.parent.exists()
    capture.subscribe()
    assert output.parent.is_dir()
    capture.close()


@pytest.mark.parametrize("tcp", [False, True])
@pytest.mark.parametrize("teardown", ["exhaust", "close", "throw"])
def test_capture_factories_keep_labels_and_cleanup(tmp_path, fake_process, tcp, teardown):
    config = {"file_name": str(tmp_path / "factory.dlt"), "binary_path": "fake"}
    factory = make_receive_tcp if tcp else make_receive
    provider = factory(SimpleNamespace(host="192.0.2.2", port=13490), config) if tcp else factory(config)
    capture = next(provider)
    assert type(capture) is DltCapture
    assert capture.transport is (Transport.TCP if tcp else Transport.UDP)
    assert not capture.is_active()
    capture.subscribe()
    if teardown == "exhaust":
        with pytest.raises(StopIteration):
            next(provider)
    elif teardown == "close":
        provider.close()
    else:
        with pytest.raises(ValueError, match="provider failure"):
            provider.throw(ValueError("provider failure"))
    assert not capture.is_active()
    fake_process[1].assert_called_once_with()


def test_tcp_reaches_the_daemon_on_the_endpoints_published_port():
    capture = DltCapture({"binary_path": "dlt-receive"}, SimpleNamespace(host="127.0.0.1", port=40123))
    assert capture._env["DLT_DAEMON_TCP_PORT"] == "40123"


def test_tcp_asks_the_endpoint_for_its_port_again_when_it_starts(monkeypatch):
    endpoint = SimpleNamespace(host="127.0.0.1", port=40123)
    capture = DltCapture({"binary_path": "dlt-receive"}, endpoint)
    endpoint.port = 40124  # the container restarted and is published elsewhere
    monkeypatch.setattr(type(capture).__mro__[1], "__enter__", lambda self: self)
    capture.subscribe()
    assert capture._env["DLT_DAEMON_TCP_PORT"] == "40124"


def test_tcp_probe_invalidates_a_live_receiver_when_the_published_port_changes(tmp_path, fake_process):
    endpoint = SimpleNamespace(host="127.0.0.1", port=40123)
    capture = DltCapture({"file_name": str(tmp_path / "capture.dlt"), "binary_path": "fake"}, endpoint)
    start, stop = fake_process
    capture.subscribe()
    assert capture.is_active()

    endpoint.port = 40124

    assert not capture.is_active()
    capture.subscribe()
    assert start.call_count == 2
    assert stop.call_count == 1
    assert capture._env["DLT_DAEMON_TCP_PORT"] == "40124"
    assert capture.is_active()
    capture.close()


def test_lines_reports_a_dead_subscribed_stream(tmp_path, fake_process, monkeypatch):
    capture = DltCapture({"file_name": str(tmp_path / "capture.dlt"), "binary_path": "fake"}, _tcp().endpoint)
    capture.subscribe()
    monkeypatch.setattr(ProcessWrapper, "is_running", lambda self: False)

    with pytest.raises(RuntimeError, match="stream is no longer active"):
        capture.lines()

    capture.close()
