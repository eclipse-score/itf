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

from score.itf.core.com.ssh import execute_command


logger = logging.getLogger(__name__)


def pre_tests_phase(target):
    _check_ping(target, check_timeout=10)
    _check_ssh_is_up(target, check_timeout=5, check_n_retries=5)
    _check_sftp_is_up(target)
    # TODO Add more checks in pre_tests_phase


def _check_ping(target, check_timeout: int = 180):
    """Checks whether the target can be pinged.

    :param Target target: Target to ping.
    :param boolext_ip: Use external IP address. Default: False.
    :param int check_timeout: How long to wait for check to succeed. Default: 180.
    :raises AssertionError: If the target cannot be pinged within the specified time-frame.
    """
    result = target.ping(timeout=check_timeout)
    assert result, f"Target is not pingable within expected time frame"
    logger.info("Check target ping: OK")


def _check_ssh_is_up(target, check_timeout: int = 15, check_n_retries: int = 5):
    """Check whether the target can be reached via SSH.

    :param Target target: Target to reach via SSH.
    :param bool ext_ip: Use external IP address. Default: False.
    :param int check_timeout: How long to wait for check to succeed. Default: 15.
    :param int check_n_retries: How many times to re-try the check. Default: 5.
    :raises AssertionError: If the SSH command fails within the specified time-frame.
    """
    with target.ssh(timeout=check_timeout, n_retries=check_n_retries, retry_interval=2) as ssh:
        result = execute_command(ssh, "echo Qnx_S-core!")
    assert result == 0, "Running SSH command on the target failed"
    logger.info("Check target ssh: OK")


def _check_sftp_is_up(target):
    """Check whether the target can be reached via SFTP.

    :param Target target: Target to reach via SFTP.
    :param bool ext_ip: Use external IP address. Default: False.
    """
    with target.sftp() as sftp:
        result = sftp.list_dirs_and_files("/")
    assert result, "Running SFTP command on the target failed"
    logger.info("Check target sftp: OK")
