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

from itf.plugins.utils.bazel import get_output_dir
from itf.plugins.utils.process.process_wrapper import ProcessWrapper


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
        target_ip: str,
        protocol: Protocol = Protocol.UDP,
        file_name: str = None,
        enable_file_output: bool = True,
        print_to_stdout: bool = False,
        logger_name: str = None,
        sctf: bool = False,
        data_router_config: dict = None,
        binary_path: str = None,
    ):
        """Initialize DltReceive instance.

        :param str target_ip: IP address of the target to receive DLT logs from.
        :param Protocol protocol: Protocol to use for receiving DLT logs (TCP or UDP).
        :param str file_name: Optional name for the output DLT file. If not provided, defaults to "dlt_receive.dlt" in the output directory.
        :param bool enable_file_output: If True, DLT logs will be saved to a file.
        :param bool print_to_stdout: If True, DLT logs will be printed to stdout.
        :param str logger_name: Optional name for the logger. If not provided, defaults to the basename of the binary path.
        :param bool sctf: If True, uses SCTF-specific configurations.
        :param dict data_router_config: Configuration for the data router
         with keys "vlan_address" and "multicast_addresses".
        :param str binary_path: Path to the DLT receive binary.
        """
        self._target_ip = target_ip
        self._protocol = protocol
        self._dlt_file_name = file_name or f"{get_output_dir()}/dlt_receive.dlt"

        self._data_router_config = data_router_config
        self._protocol_opts = DltReceive.protocol_arguments(
            self._target_ip, self._protocol, sctf, self._data_router_config
        )

        dlt_receive_args = ["-o", self._dlt_file_name] if enable_file_output else []
        dlt_receive_args += self._protocol_opts
        dlt_receive_args += ["-a"] if print_to_stdout else []

        if file_name and enable_file_output:
            DltReceive.remove_dlt_file(self._dlt_file_name)

        super().__init__(
            binary_path,
            dlt_receive_args,
            logger_name=logger_name,
        )

    @staticmethod
    def remove_dlt_file(target_file):
        if os.path.exists(target_file):
            os.remove(target_file)

    @staticmethod
    def protocol_arguments(target_ip, protocol, sctf, data_router_config):
        dlt_port = "3490"
        proto_specific_opts = []

        if protocol == Protocol.TCP:
            proto_specific_opts = ["--tcp", target_ip]
        elif protocol == Protocol.UDP:
            net_if = target_ip if sctf else data_router_config["vlan_address"]
            mcasts = data_router_config["multicast_addresses"]
            mcast_ip = [val for pair in zip(["--mcast-ip"] * len(mcasts), mcasts) for val in pair]
            proto_specific_opts = ["--udp"] + mcast_ip + ["--net-if", net_if, "--port", dlt_port]
        else:
            raise RuntimeError(
                f"Unsupported Transport Layer Protocol provided: {protocol}. "
                + "Supported are: "
                + "["
                + ", ".join([str(name[1]) for name in Protocol.__members__.items()])
                + "]"
            )

        return proto_specific_opts

    def file_name(self):
        return self._dlt_file_name
