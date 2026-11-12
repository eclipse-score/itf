# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
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
"""Targets with a second login (`qnx_shell`, the QEMU QNX target): each login is a role of its own."""

import score.itf as itf


@itf.requires("qnx_shell")
def test_a_second_login_runs_commands_as_its_own_user(target):
    with target.qnx_shell as ssh:  # bring-up opens the main shell only
        assert ssh.execute_command("echo 'Username:' $USER && uname -a") == 0
