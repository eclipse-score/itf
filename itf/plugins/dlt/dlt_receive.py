# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
from enum import Enum, auto
import logging
import os

from itf.core.utils.bazel import get_output_dir
from itf.core.utils.process.process_wrapper import ProcessWrapper


logger = logging.getLogger(__name__)


class Protocol(Enum):
    TCP = auto()
    UDP = auto()


class DltReceive(ProcessWrapper):
    """
    Save DLT logs from the provided target
    Logs are saved in the active folder
    During tests execution the active folder is "bazel-testlogs/<test_path>/<test_name>/test.outputs/"
    "protocol" can be either Protocol.TCP or Protocol.UDP
    """

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
        """Initialize DltReceive instance.

        :param Protocol protocol: Protocol to use for receiving DLT logs (TCP or UDP).
        :param str host_ip: IP address to bind to in case of UDP.
        :param list[str] multicast_ips: Multicast IPs to join to in case of UDP.
        :param str target_ip: IP address to connect to in case of TCP.
        :param str file_name: Optional name for the output DLT file. If not provided, defaults to "dlt_receive.dlt" in the output directory.
        :param bool enable_file_output: If True, DLT logs will be saved to a file.
        :param bool print_to_stdout: If True, DLT logs will be printed to stdout.
        :param str logger_name: Optional name for the logger. If not provided, defaults to the basename of the binary path.
        :param str binary_path: Path to the DLT receive binary.
        """
        self._dlt_file_name = file_name or f"{get_output_dir()}/dlt_receive.dlt"

        dlt_receive_args = ["-o", self._dlt_file_name] if enable_file_output else []
        dlt_receive_args += _protocol_arguments(protocol, host_ip, target_ip, multicast_ips)
        dlt_receive_args += ["-a"] if print_to_stdout else []

        if self._dlt_file_name and enable_file_output:
            if os.path.exists(self._dlt_file_name):
                os.remove(self._dlt_file_name)

        super().__init__(
            binary_path,
            dlt_receive_args,
            logger_name=logger_name,
        )

    def file_name(self):
        return self._dlt_file_name


def _protocol_arguments(protocol, host_ip, target_ip, multicast_ips):
    dlt_port = "3490"
    proto_specific_opts = []

    if protocol == Protocol.TCP:
        proto_specific_opts = ["--tcp", target_ip]
    elif protocol == Protocol.UDP:
        mcast_ip = [val for pair in zip(["--mcast-ip"] * len(multicast_ips), multicast_ips) for val in pair]
        proto_specific_opts = ["--udp"] + ["--net-if", host_ip, "--port", dlt_port] + mcast_ip
    else:
        raise RuntimeError(
            f"Unsupported Transport Layer Protocol provided: {protocol}. "
            + "Supported are: "
            + "["
            + ", ".join([str(name[1]) for name in Protocol.__members__.items()])
            + "]"
        )

    return proto_specific_opts
