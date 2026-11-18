"""The same capture scenario runs against guest or localhost traffic."""

import subprocess
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import score.itf as itf


class Capture(Protocol):
    __contract__ = "observe.capture"

    def window(self, name: str, *, ready_timeout: float = 5.0) -> AbstractContextManager[Path]: ...


class PacketReader(Protocol):
    __contract__ = "integration.packet_reader"

    def read(self, path: Path) -> str: ...


class Traffic(Protocol):
    __contract__ = "integration.traffic"
    host: str
    port: int

    def send(self, payload: bytes, host: str, port: int) -> None: ...


itf_requires = [
    itf.requires("capture", shape=Capture),
    itf.requires("packet_reader", shape=PacketReader),
    itf.requires("traffic", shape=Traffic),
]


def capture_payload(target, token: str) -> Path:
    with target.capture.window(token) as path:
        target.traffic.send(token.encode("ascii"), target.traffic.host, target.traffic.port)
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            try:
                if token in target.packet_reader.read(path):
                    return path
            except subprocess.CalledProcessError:
                pass
            time.sleep(0.05)
        raise AssertionError(f"UDP payload {token!r} did not reach capture {path}")


def test_capture_window_records_udp_payload(target):
    token = f"itf-capture-{uuid4().hex}"
    path = capture_payload(target, token)
    assert path.is_file() and path.stat().st_size > 24
    assert token in target.packet_reader.read(path)


def test_capture_windows_do_not_include_previous_traffic(target):
    first, second = "first-" + uuid4().hex, "second-" + uuid4().hex
    first_path = capture_payload(target, first)
    second_path = capture_payload(target, second)
    assert first_path != second_path
    assert first in target.packet_reader.read(first_path)
    assert second in target.packet_reader.read(second_path)
    assert first not in target.packet_reader.read(second_path)
