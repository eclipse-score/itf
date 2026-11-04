"""Project UDP fixtures and host-side readback, independent of observability packs."""

import ipaddress
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from score.itf.core import capability, hookimpl, state


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str) -> tuple[int, bytes]: ...


@dataclass(frozen=True)
class TrafficConfig:
    host: str = "169.254.21.88"
    port: int = 3491
    sender: str = "/proc/boot/udp_sender"


class Traffic:
    host: str
    port: int

    def __init__(self, command: Command, config: TrafficConfig):
        self.command = command
        self.config = config
        self.host = config.host
        self.port = config.port

    def send(self, payload: bytes, host: str, port: int) -> None:
        address = str(ipaddress.IPv4Address(host))
        if not 1 <= port <= 65535:
            raise ValueError("UDP port must be between 1 and 65535")
        if not payload or len(payload) > 65507:
            raise ValueError("UDP payload must contain between 1 and 65507 bytes")
        octals = "".join(f"\\{value:03o}" for value in payload)
        code, output = self.command.exec(
            f"printf {shlex.quote(octals)} | {shlex.quote(self.config.sender)} {shlex.quote(address)} {port}"
        )
        if code != 0:
            raise RuntimeError(f"UDP emission failed (exit {code}): {output!r}")


@capability("integration.traffic", label="traffic")
def make_traffic(command: Command, config: TrafficConfig) -> Traffic:
    return Traffic(command, TrafficConfig(**config))


@dataclass(frozen=True)
class PacketReaderConfig:
    binary_path: str = "tcpdump"
    timeout: float = 5.0


@dataclass(frozen=True)
class PacketReader:
    config: PacketReaderConfig

    def read(self, path: Path) -> str:
        result = subprocess.run(
            [self.config.binary_path, "-n", "-A", "-r", str(path)],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=self.config.timeout,
            check=True,
        )
        return result.stdout


@capability("integration.packet_reader", label="packet_reader")
def make_packet_reader(config: PacketReaderConfig) -> PacketReader:
    return PacketReader(PacketReaderConfig(**config))


class CaptureEvidence(Protocol):
    __contract__ = "observe.capture"

    def running(self) -> bool: ...
    def stop(self) -> None: ...
    def path(self) -> Path | None: ...


class ConsoleEvidence(Protocol):
    __contract__ = "exec.console"

    def lines(self, since: int = 0) -> list[str]: ...


itf_expect = [CaptureEvidence, ConsoleEvidence]


class Console(Protocol):
    __contract__ = "exec.console"

    def open(self) -> None: ...
    def close(self) -> None: ...
    def is_open(self) -> bool: ...


class Platform(Protocol):
    __contract__ = "platform.instance"

    def running(self) -> bool: ...


@state("console.open", label="open_serial_console")
def open_serial_console(console: Console, platform: Platform) -> None:
    console.close()
    deadline = time.monotonic() + 10
    while True:
        try:
            console.open()
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


@open_serial_console.probe
def serial_console_open(console: Console, platform: Platform) -> bool:
    return platform.running() and console.is_open()


@hookimpl
def itf_verify(session):
    target = session.target
    code, output = target.command.exec("echo -n ready")
    session.check("observability.command.answers", code == 0 and output == b"ready")
    if target.has("capture"):
        session.check("observability.capture.running", target.capture.running())


@hookimpl
def itf_teardown(session):
    target = session.target
    artifacts = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "artifacts")) / "observability"
    artifacts.mkdir(parents=True, exist_ok=True)
    if target.has("console"):
        (artifacts / "console.txt").write_text("\n".join(target.console.lines()), encoding="utf-8")
    if target.has("capture"):
        target.capture.stop()
        path = target.capture.path()
        if path is not None and path.is_file():
            destination = artifacts / "capture.pcap"
            if path.resolve() != destination.resolve():
                shutil.copy2(path, destination)
