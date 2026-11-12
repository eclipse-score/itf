"""Renew a managed platform and observe fresh traffic through its restored goals."""

import subprocess
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import pytest

import score.itf as itf


class Platform(Protocol):
    __contract__ = "platform.instance"

    def running(self) -> bool: ...


class Capture(Protocol):
    __contract__ = "observe.capture"

    def running(self) -> bool: ...
    def window(self, name: str, *, ready_timeout: float = 5.0) -> AbstractContextManager[Path]: ...


class PacketReader(Protocol):
    __contract__ = "integration.packet_reader"

    def read(self, path: Path) -> str: ...


class Traffic(Protocol):
    __contract__ = "integration.traffic"
    host: str
    port: int

    def send(self, payload: bytes, host: str, port: int) -> None: ...


@pytest.fixture
def observe_traffic(target):
    def observe(phase: str) -> None:
        assert target.platform.running()
        assert target.capture.running()
        token = f"itf-renew-{phase}-{uuid4().hex}"
        with target.capture.window(token) as path:
            target.traffic.send(token.encode("ascii"), target.traffic.host, target.traffic.port)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                try:
                    captured = token in target.packet_reader.read(path)
                except subprocess.CalledProcessError:
                    captured = False
                if captured:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError(f"network observability did not recover during {phase}")
        assert token in target.packet_reader.read(path)

    return observe


@itf.requires("platform", shape=Platform)
@itf.requires("capture", shape=Capture)
@itf.requires("packet_reader", shape=PacketReader)
@itf.requires("traffic", shape=Traffic)
def test_renew_platform_restores_network_observability(target, observe_traffic):
    observe_traffic("before")
    target.renew("platform")
    observe_traffic("after")
