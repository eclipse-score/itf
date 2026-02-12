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
from contextlib import contextmanager, nullcontext

from score.itf.plugins.core import Target
from score.itf.plugins.qemu.qemu_process import QemuProcess

from score.itf.core.com.ssh import Ssh
from score.itf.core.com.sftp import Sftp
from score.itf.core.com.ping import ping, ping_lost


QEMU_CAPABILITIES = ["ssh", "sftp"]


class QemuTarget(Target):
    def __init__(self, process, config):
        super().__init__(capabilities=QEMU_CAPABILITIES)
        self._process = process
        self._config = config

    def kill_process(self):
        self._process.stop()

    def restart_process(self):
        self._process.restart()

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
        ssh_ip = self._config.networks[0].ip_address
        ssh_port = port if port else self._config.ssh_port
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

    def sftp(self, ssh_connection=None):
        ssh_ip = self._config.networks[0].ip_address
        ssh_port = self._config.ssh_port
        return Sftp(ssh_connection, ssh_ip, ssh_port)

    def ping(self, timeout, wait_ms_precision=None):
        return ping(
            address=self._config.networks[0].ip_address,
            timeout=timeout,
            wait_ms_precision=wait_ms_precision,
        )

    def ping_lost(self, timeout, interval=1, wait_ms_precision=None):
        return ping_lost(
            address=self._config.networks[0].ip_address,
            timeout=timeout,
            interval=interval,
            wait_ms_precision=wait_ms_precision,
        )


@contextmanager
def qemu_target(test_config):
    """Context manager for QEMU target setup."""
    with QemuProcess(
        test_config.qemu_image,
        test_config.qemu_config.qemu_ram_size,
        test_config.qemu_config.qemu_num_cores,
        network_adapters=[adapter.name for adapter in test_config.qemu_config.networks],
        port_forwarding=test_config.qemu_config.port_forwarding
        if hasattr(test_config.qemu_config, "port_forwarding")
        else [],
    ) if test_config.qemu_image else nullcontext() as qemu_process:
        target = QemuTarget(qemu_process, test_config.qemu_config)
        yield target
