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
import logging

from score.itf.plugins.qemu.base.target.config.base_processor import BaseProcessor
from score.itf.plugins.qemu.base.os.operating_system import OperatingSystem

from score.itf.core.com.sftp import Sftp
from score.itf.core.com.ssh import Ssh
from score.itf.core.com.ping import ping, ping_lost


logger = logging.getLogger(__name__)


class TargetProcessor:
    """Represents single unit which tests can communicate with."""

    def __init__(self, processor: BaseProcessor, os: OperatingSystem, diagnostic_ip=None):
        self.__type = processor
        self.__os = os
        self.__config = processor
        self.__diagnostic_ip = diagnostic_ip
        self.__ip_address = self.__config.ip_address
        self.__ext_ip_address = (
            self.__config.ext_ip_address if hasattr(self.__config, "ext_ip_address") else self.__ip_address
        )

    def __repr__(self):
        return f"Processor, type: {self.__type.name}, config: {self.__config}"

    @property
    def config(self):
        return self.__config

    @property
    def type(self):
        return self.__type

    # pylint: disable=C0103
    @property
    def os(self):
        return self.__os

    @property
    def diagnostic_ip(self):
        return self.__diagnostic_ip

    @diagnostic_ip.setter
    def diagnostic_ip(self, value):
        self.__diagnostic_ip = value

    @property
    def diagnostic_ip_address(self):
        return self.__config.diagnostic_ip_address

    @property
    def diagnostic_address(self):
        return self.__config.diagnostic_address

    @property
    def ip_address(self):
        return self.__ip_address

    @property
    def ssh_port(self):
        return self.__config.ssh_port

    @ip_address.setter
    def ip_address(self, value):
        self.__ip_address = value

    @property
    def ext_ip_address(self):
        return self.__ext_ip_address

    def uses_doip(self):
        return self.__config.use_doip

    def ssh(
        self,
        timeout: int = 15,
        port: int = None,
        n_retries: int = 5,
        retry_interval: int = 1,
        pkey_path: str = "",
        username: str = "root",
        password: str = "",
        ext_ip: bool = False,
    ):
        """Create SSH connection to target.

        :param int timeout: Connection timeout in seconds. Default is 15 seconds.
        :param int port: SSH port, if None use default port from config.
        :param int n_retries: Number of retries to connect. Default is 5 retries.
        :param int retry_interval: Interval between retries in seconds. Default is 1 second.
        :param str pkey_path: Path to private key file. If empty, password authentication is used.
        :param str username: SSH username. Default is 'root'.
        :param str password: SSH password.
        :param bool ext_ip: Use external IP address if True, otherwise use internal IP address.
        :return: Ssh connection object.
        :rtype: Ssh
        """
        ssh_ip = self.ext_ip_address if ext_ip else self.ip_address
        ssh_port = port if port else self.ssh_port
        return Ssh(
            target_ip=ssh_ip,
            port=ssh_port,
            timeout=timeout,
            n_retries=n_retries,
            retry_interval=retry_interval,
            pkey_path=pkey_path,
            username=username,
            password=password,
        )

    def sftp(self, ssh_connection=None, ext_ip=False, port=None):
        ssh_ip = self.ext_ip_address if ext_ip else self.ip_address
        ssh_port = port if port else self.ssh_port
        return Sftp(ssh_connection, ssh_ip, ssh_port)

    def ping(self, timeout, ext_ip=False, wait_ms_precision=None):
        return ping(
            address=self.ext_ip_address if ext_ip else self.ip_address,
            timeout=timeout,
            wait_ms_precision=wait_ms_precision,
        )

    def ping_lost(self, timeout, interval=1, ext_ip=False, wait_ms_precision=None):
        return ping_lost(
            address=self.ext_ip_address if ext_ip else self.ip_address,
            timeout=timeout,
            interval=interval,
            wait_ms_precision=wait_ms_precision,
        )

    def login(self):
        pass

    def teardown(self):
        pass
