"""Process-based DLT receiver and shared transport arguments."""

import os
import tempfile
from enum import Enum, auto

from score.itf.core.process import ProcessWrapper


DLT_PORT = "3490"


class Protocol(Enum):
    TCP = auto()
    UDP = auto()


def protocol_arguments(protocol, host_ip, target_ip, multicast_ips):
    if protocol == Protocol.TCP:
        return ["--tcp", target_ip]
    if protocol == Protocol.UDP:
        multicast = [arg for ip in multicast_ips for arg in ("--mcast-ip", ip)]
        return ["--udp", "--net-if", host_ip, "--port", DLT_PORT, *multicast]
    raise RuntimeError(
        f"Unsupported Transport Layer Protocol provided: {protocol}. "
        + "Supported are: ["
        + ", ".join(str(member) for member in Protocol)
        + "]"
    )


def bundled(name: str) -> str:
    """Resolve a bundled Bazel tool, falling back to PATH."""
    try:
        from python.runfiles import runfiles
    except ImportError:
        return name
    located_files = runfiles.Create()
    located = located_files.Rlocation(f"score_itf/score/itf/packs/dlt/{name}") if located_files else None
    return located if located and os.path.exists(located) else name


def output_dir() -> str:
    return os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR") or tempfile.gettempdir()


class DltReceive(ProcessWrapper):
    def __init__(
        self,
        protocol: Protocol = Protocol.UDP,
        host_ip: str = None,
        multicast_ips: list[str] = None,
        target_ip: str = None,
        file_name: str = None,
        enable_file_output: bool = True,
        print_to_stdout: bool = False,
        logger_name: str = None,
        binary_path: str = None,
    ):
        self._dlt_file_name = file_name or f"{output_dir()}/dlt_receive.dlt"
        args = ["-o", self._dlt_file_name] if enable_file_output else []
        args += protocol_arguments(protocol, host_ip, target_ip, multicast_ips)
        args += ["-a"] if print_to_stdout else []
        if enable_file_output and os.path.exists(self._dlt_file_name):
            os.remove(self._dlt_file_name)
        super().__init__(binary_path or bundled("dlt-receive"), args, logger_name=logger_name)

    def file_name(self):
        return self._dlt_file_name
