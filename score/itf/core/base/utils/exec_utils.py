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

# pylint: disable=unused-argument

import logging

from score.itf.core.base.target.base_target import Target
from score.itf.core.com.ssh import execute_command


logger = logging.getLogger(__name__)


def pre_tests_phase(target, ip_address, test_config, request):
    __check_ping(target=target, check_timeout=60)
    __check_ssh_is_up(target=target, ext_ip=test_config.os.value.ssh_uses_ext_ip, check_timeout=10, check_n_retries=5)
    __check_sftp_is_up(target=target, ext_ip=test_config.os.value.ssh_uses_ext_ip)
    # TODO Add more checks in pre_tests_phase


def post_tests_phase(target, test_config):
    # TODO post_tests_phase will be implemented later
    pass


def __check_ping(target: Target, ext_ip: bool = False, check_timeout: int = 180):
    """Checks whether the target can be pinged.

    :param Target target: Target to ping.
    :param boolext_ip: Use external IP address. Default: False.
    :param int check_timeout: How long to wait for check to succeed. Default: 180.
    :raises AssertionError: If the target cannot be pinged within the specified time-frame.
    """
    result = target.sut.ping(timeout=check_timeout, ext_ip=ext_ip)
    assert result, f"{target.sut.type} is not pingable within expected time frame"
    logger.info("Check target ping: OK")


def __check_ssh_is_up(target: Target, ext_ip: bool = False, check_timeout: int = 15, check_n_retries: int = 5):
    """Check whether the target can be reached via SSH.

    :param Target target: Target to reach via SSH.
    :param bool ext_ip: Use external IP address. Default: False.
    :param int check_timeout: How long to wait for check to succeed. Default: 15.
    :param int check_n_retries: How many times to re-try the check. Default: 5.
    :raises AssertionError: If the SSH command fails within the specified time-frame.
    """
    with target.sut.ssh(timeout=check_timeout, n_retries=check_n_retries, retry_interval=2, ext_ip=ext_ip) as ssh:
        result = execute_command(ssh, "echo Qnx_S-core!")
    assert result == 0, "Running SSH command on the target failed"
    logger.info("Check target ssh: OK")


def __check_sftp_is_up(target: Target, ext_ip: bool = False):
    """Check whether the target can be reached via SFTP.

    :param Target target: Target to reach via SFTP.
    :param bool ext_ip: Use external IP address. Default: False.
    """
    with target.sut.sftp(ext_ip=ext_ip) as sftp:
        result = sftp.list_dirs_and_files("/")
    assert result, "Running SFTP command on the target failed"
    logger.info("Check target sftp: OK")
