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

import pytest

from score.itf.core.com.ping import ping


def test_ping_raises_when_ping_utility_is_missing(mocker):
    mocker.patch("score.itf.core.com.ping.shutil.which", return_value=None)
    with pytest.raises(RuntimeError, match="'ping' utility is not installed"):
        ping("127.0.0.1")


def test_ping_returns_true_when_host_is_reachable(mocker):
    mocker.patch("score.itf.core.com.ping.shutil.which", return_value="/usr/bin/ping")
    mocker.patch("score.itf.core.com.ping.os.system", return_value=0)
    assert ping("127.0.0.1") is True


def test_ping_returns_false_when_host_is_unreachable(mocker):
    mocker.patch("score.itf.core.com.ping.shutil.which", return_value="/usr/bin/ping")
    mocker.patch("score.itf.core.com.ping.os.system", return_value=1)
    assert ping("192.0.2.1") is False
