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

from types import SimpleNamespace

import pytest

from score.itf.core.com.ssh import Ssh
from score.itf.plugins.qemu.qemu import Qemu
from score.itf.plugins.qemu.config import SshAuth
from score.itf.plugins.qemu.qemu_target import QemuTarget


@pytest.fixture
def qemu_target():
    config = SimpleNamespace(
        networks=[SimpleNamespace(ip_address="127.0.0.1")],
        ssh_port=22,
    )
    return QemuTarget(process=None, config=config)


def build_ssh_auth_args(password, pkey_path):
    return {k: v for k, v in locals().items() if v is not None}


def build_assert_msg(uc, username, passowrd, pkey_path):
    items = ",".join([f"{k}:{v}" for k, v in locals().items()][1:])

    return f"failed to assert {uc} for {items}"


@pytest.mark.parametrize(
    "username,password,pkey_path,expected",
    [
        ("otheruser", None, None, {"username": "otheruser"}),
        ("qnxuser", "qnxuser", None, {"username": "qnxuser", "password": "qnxuser"}),
        ("root", None, "mykey", {"username": "root", "pkey_path": "mykey"}),
    ],
)
def test_resolve_ssh_auth_ok(qemu_target, username, password, pkey_path, expected):
    ssh_opts = build_ssh_auth_args(password, pkey_path)

    assert qemu_target._resolve_ssh_auth(username, **ssh_opts) == expected, build_assert_msg(
        "ssh auth dict", username, password, pkey_path
    )


@pytest.mark.parametrize(
    "username,password,pkey_path,err_msg",
    [
        (None, "password", None, "Missing or invalid SSH username value"),
        ("", "password", None, "Missing or invalid SSH username value"),
    ],
)
def test_resolve_ssh_auth_err(qemu_target, username, password, pkey_path, err_msg):
    ssh_opts = build_ssh_auth_args(password, pkey_path)

    with pytest.raises(ValueError) as excinfo:
        qemu_target._resolve_ssh_auth(username, **ssh_opts)

    assert str(excinfo.value) == err_msg, build_assert_msg("error message", username, password, pkey_path)
