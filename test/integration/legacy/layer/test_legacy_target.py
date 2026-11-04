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
"""The compatibility layer's original target is a facade over the roles, with the original capabilities."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from score.itf.compat import legacy
from score.itf.compat.legacy import LegacyTarget, QemuTarget
from score.itf.compat.plugins import targets as legacy_targets
from score.itf.core import Session as ItfSession


class Command:
    def exec(self, cmd, timeout=30.0):
        return 0, f"ran {cmd}".encode()


class Handle:
    """Stands in for the target handle: roles by name, plus a method of its own."""

    def __init__(self, **roles):
        self.roles = roles

    def has(self, name):
        return name in self.roles

    def names(self):
        return tuple(sorted(self.roles))

    def get(self, name):
        return self.roles[name]

    def reach(self, *states):
        return set(states)

    def __getattr__(self, name):
        try:
            return self.roles[name]
        except KeyError:
            raise AttributeError(name) from None


def test_the_original_target_is_a_facade_with_the_original_capabilities():
    target = LegacyTarget(Handle(command=Command(), files=object()))
    assert target.execute("ls") == (0, b"ran ls")
    assert target.get_capabilities() == {"exec", "file_transfer"}
    with pytest.raises(NotImplementedError, match="'platform' role"):
        target.restart()


@pytest.mark.parametrize(
    ("docker_ssh", "dlt", "target_file"),
    [
        (False, False, "docker.itf.yaml"),
        (False, True, "docker_dlt.itf.yaml"),
        (True, False, "docker_ssh.itf.yaml"),
        (True, True, "docker_ssh_dlt.itf.yaml"),
    ],
)
def test_docker_plugin_selects_ssh_target_only_when_enabled(monkeypatch, docker_ssh, dlt, target_file):
    class Config:
        option = SimpleNamespace(itf_target=None)

        def getoption(self, name):
            return {
                "docker_ssh": docker_ssh,
                "dlt_config": None,
                "dlt_receive_path": "dlt-receive" if dlt else None,
                "dlt_receive_on_target_path": None,
                "itf_target": None,
            }.get(name)

    monkeypatch.setattr(legacy_targets.os, "environ", {})
    config = Config()

    legacy_targets.select(config, "docker", {"LEGACY_DOCKER_IMAGE": "image"})

    assert Path(config.option.itf_target).name == target_file


def test_default_docker_target_does_not_advertise_ssh():
    target_file = Path(legacy.__file__).parent / "targets" / "docker.itf.yaml"
    target = yaml.safe_load(target_file.read_text(encoding="utf-8"))

    assert "ssh" not in target["packs"]
    assert {"endpoint", "credentials", "shell", "sftp"}.isdisjoint(target["capabilities"])


@pytest.mark.parametrize("method", ["restart", "restart_process"])
def test_qemu_restart_uses_the_managed_platform_lifecycle(method, monkeypatch):
    handle = Handle(platform=object())
    renewed = []
    monkeypatch.setattr(Handle, "renew", lambda self, *roles: renewed.append(roles), raising=False)
    target = QemuTarget(handle)

    assert getattr(target, method)() is None
    assert renewed == [("platform",)]


def test_qemu_restart_rebuilds_dependents_and_reaches_the_goals(tmp_path, monkeypatch):
    from score.itf.packs.qemu.platform import QemuPlatform
    from score.itf.packs.ssh import client, steps

    events = []

    def start(platform):
        platform.active = True
        events.append("start")

    def stop(platform):
        platform.active = False
        events.append("stop")

    def connect(*args, **kwargs):
        events.append("connect")
        return SimpleNamespace(
            get_transport=lambda: SimpleNamespace(is_active=lambda: True),
            close=lambda: events.append("disconnect"),
        )

    monkeypatch.setattr(QemuPlatform, "start", start)
    monkeypatch.setattr(QemuPlatform, "stop", stop)
    monkeypatch.setattr(QemuPlatform, "running", lambda platform: getattr(platform, "active", False))
    monkeypatch.setattr(client, "connect", connect)
    monkeypatch.setattr(steps, "accepts_connections", lambda endpoint: True)
    config = tmp_path / "qemu.json"
    config.write_text(
        json.dumps(
            {
                "networks": [{"name": "lo", "ip_address": "127.0.0.1", "gateway": "127.0.0.1"}],
                "ssh_port": 2222,
                "qemu_num_cores": 2,
                "qemu_ram_size": "1G",
            }
        )
    )
    monkeypatch.setenv("LEGACY_QEMU_CONFIG", str(config))
    monkeypatch.setenv("LEGACY_QEMU_KERNEL", str(tmp_path / "kernel"))
    monkeypatch.delenv("LEGACY_QEMU_ROOTFS", raising=False)
    monkeypatch.delenv("LEGACY_QEMU_DISK", raising=False)
    session = ItfSession(
        target=Path(legacy.__file__).parent / "targets" / "qemu.itf.yaml",
        overrides=["policies: []"],
        artifacts="none",
    ).resolve()
    try:
        session.bring_up()
        roles = ("platform", "endpoint", "credentials", "shell", "command", "process", "files")
        before = {name: session.target.get(name) for name in roles}

        QemuTarget(session.target).restart()

        assert all(session.target.get(name) is not before[name] for name in roles)
        assert not before["shell"].is_connected()
        assert session.target.shell.is_connected()
        assert session.target.command.shell is session.target.shell
        assert session.target.process.shell is session.target.shell
        assert session.target.files._ssh is session.target.shell
        assert session.target.states() >= {"platform.up", "shell.open", "network.reachable"}
        assert events == ["start", "connect", "disconnect", "stop", "start", "connect"]
    finally:
        session.close()


class Platform:
    def running(self):
        return True


class Session:
    """Stands in for the session the compatibility policy's itf_verify gets: a target and check()."""

    def __init__(self, target):
        self.target, self.checks = target, {}

    def check(self, name, ok, detail=""):
        self.checks[name] = ok


def test_the_compatibility_policy_checks_the_command_answers_with_bytes():
    # The QEMU compatibility targets run this check at startup; command.exec returns bytes.
    import importlib.util
    from pathlib import Path

    import score.itf.compat

    path = Path(score.itf.compat.__file__).parent / "targets" / "policy.py"
    spec = importlib.util.spec_from_file_location("compat_policy_under_test", path)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)

    class Ready:
        def exec(self, cmd, timeout=30.0):
            return 0, b"ready"

    session = Session(Handle(command=Ready(), platform=Platform()))
    session.target.names = lambda: ("command", "platform")
    policy.itf_verify(session)
    assert session.checks == {"command.answers": True}
