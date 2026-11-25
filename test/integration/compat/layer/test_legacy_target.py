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
from itertools import product
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


def test_docker_target_execute_preserves_docker_exec_result():
    from docker.models.containers import ExecResult

    target = legacy.DockerTarget(Handle(command=Command()))

    result = target.execute("ls")

    assert isinstance(result, ExecResult)
    assert result.exit_code == 0
    assert result.output == b"ran ls"


def test_docker_target_preserves_its_docker_network_object():
    network = object()
    target = legacy.DockerTarget(Handle(platform=SimpleNamespace(network=network)))

    assert target.network is network


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


def test_docker_configuration_forwards_explicit_sdk_kwargs(monkeypatch):
    from score.itf.compat.plugins import docker as docker_plugin

    platform = SimpleNamespace(running=lambda: False)
    reached = []
    session = SimpleNamespace(target=Handle(platform=platform), reach=lambda state: reached.append(state))
    monkeypatch.setattr(docker_plugin, "itf_session", lambda config: session)
    monkeypatch.setattr(docker_plugin, "_applied", {})
    request = SimpleNamespace(config=SimpleNamespace(getoption=lambda name: False))
    options = {"mem_limit": "256m"}
    fixture = docker_plugin.target_init.__wrapped__(request, {"docker_sdk_kwargs": options})
    next(fixture)
    assert platform.docker_sdk_kwargs == options
    assert reached == ["platform.up"]
    with pytest.raises(StopIteration):
        next(fixture)


def test_docker_configuration_keys_it_does_not_name_go_to_the_sdk_as_the_original_passed_them():
    from score.itf.compat.plugins.docker import sdk_passthrough

    configured = sdk_passthrough({"init": False, "mem_limit": "256m", "docker_sdk_kwargs": {"user": "1000"}})
    assert configured == {"init": False, "docker_sdk_kwargs": {"user": "1000", "mem_limit": "256m"}}
    assert sdk_passthrough({"init": False}) == {"init": False}
    with pytest.raises(pytest.UsageError, match="ITF-managed options: name"):
        sdk_passthrough({"name": "mine"})


@pytest.mark.parametrize("attempts,given,expected", [(1, 3, 3), (5, 3, 5), (1, 1, 1)])
def test_qemu_boot_attempts_become_bring_up_attempts(monkeypatch, attempts, given, expected):
    from score.itf.compat.plugins import qemu as qemu_plugin

    monkeypatch.setattr(qemu_plugin, "select", lambda *args: None)
    options = {"qemu_config": "config.json", "qemu_boot_attempts": given}
    config = SimpleNamespace(
        getoption=lambda name: options.get(name),
        option=SimpleNamespace(itf_bring_up_attempts=attempts),
    )
    qemu_plugin.pytest_configure(config)
    assert config.option.itf_bring_up_attempts == expected


def test_default_docker_target_does_not_advertise_ssh():
    target_file = Path(legacy.__file__).parent / "targets" / "docker.itf.yaml"
    target = yaml.safe_load(target_file.read_text(encoding="utf-8"))

    assert "ssh" not in target["packs"]
    assert {"endpoint", "credentials", "shell", "sftp"}.isdisjoint(target["capabilities"])


@pytest.mark.parametrize("method", ["restart", "restart_process"])
def test_qemu_restart_power_cycles_the_platform_in_place_and_reaches_the_goals(method, monkeypatch):
    events = []
    platform = SimpleNamespace(restart=lambda: events.append("restart"))
    shell = SimpleNamespace(close=lambda: events.append("close"))
    handle = Handle(platform=platform, shell=shell)
    monkeypatch.setattr(Handle, "reach", lambda self, *states: events.append(("reach", states)))
    monkeypatch.setattr(Handle, "renew", lambda self, *roles: events.append(("renew", roles)), raising=False)
    target = QemuTarget(handle)

    assert getattr(target, method)() is None
    assert events == ["close", "restart", ("reach", ())]


def test_qemu_target_exposes_the_platform_panic_state():
    target = QemuTarget(Handle(platform=SimpleNamespace(guest_panicked=True)))

    assert target.guest_panicked


def test_original_qemu_boot_and_pretest_helpers_use_the_compatibility_target():
    from score.itf.compat.qemu import boot_until_ready, pre_tests_phase

    class Ssh:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def execute_command(self, command):
            assert command == "echo Qnx_S-core!"
            return 0

    class Sftp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def list_dirs_and_files(self, path):
            assert path == "/"
            return ["home"]

    events = []
    target = SimpleNamespace(
        guest_panicked=True,
        restart=lambda: events.append("restart"),
        ping=lambda **kwargs: events.append(("ping", kwargs)) or True,
        ssh=lambda **kwargs: events.append(("ssh", kwargs)) or Ssh(),
        sftp=lambda: Sftp(),
    )
    attempts = []

    def run_checks(_target):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise RuntimeError("boot check failed")

    boot_until_ready(target, 2, run_checks)
    pre_tests_phase(target)

    assert attempts == [1, 2]
    assert events == [
        "restart",
        ("ping", {"timeout": 10}),
        ("ssh", {"timeout": 5, "n_retries": 5, "retry_interval": 2}),
    ]


def test_qemu_async_process_and_process_module_paths_reexport_the_core_ssh_process():
    from score.itf.packs.ssh.process import SshAsyncProcess
    from score.itf.plugins.qemu.qemu_process import QemuProcess
    from score.itf.plugins.qemu.qemu_target import QemuAsyncProcess, qemu_target

    assert issubclass(QemuAsyncProcess, SshAsyncProcess)
    assert callable(QemuProcess)
    assert callable(qemu_target)


def test_qemu_async_process_reuses_the_process_role_by_default():
    from score.itf.compat.legacy import QemuTarget

    calls = []
    process = object()
    provider = SimpleNamespace(spawn=lambda *args, **kwargs: calls.append((args, kwargs)) or process)
    target = QemuTarget(Handle(process=provider))
    assert target.execute_async("worker", args=["arg"], cwd="/tmp") is process
    assert calls == [(("worker",), {"args": ["arg"], "cwd": "/tmp"})]


def test_qemu_async_process_uses_a_dedicated_shell_and_closes_it_when_finished(monkeypatch):
    from score.itf.compat.legacy import QemuTarget
    from score.itf.compat.qemu import QemuAsyncProcess

    class ProcessShell:
        def execute_command(self, command):
            events.append(command)
            return 0

    class Channel:
        def exit_status_ready(self):
            return True

        def recv_exit_status(self):
            return 17

    class SshContext:
        def __enter__(self):
            events.append("ssh-open")
            return ProcessShell()

        def __exit__(self, *_args):
            events.append("ssh-close")

    class Process:
        _channel = Channel()
        _output_thread = SimpleNamespace(join=lambda: None)
        _output = ["complete"]

        def pid(self):
            return 42

    class ProcessFactory:
        def __init__(self, shell):
            assert isinstance(shell, ProcessShell)

        def spawn(self, binary_path, args=None, cwd="/", **kwargs):
            assert (binary_path, args, cwd) == ("worker", ["arg"], "/tmp")
            return Process()

    events = []
    target = QemuTarget(Handle(), async_new_connection=True)
    monkeypatch.setattr(target, "ssh", lambda **_kwargs: SshContext())
    from score.itf.packs.ssh import process as ssh_process

    monkeypatch.setattr(ssh_process, "SshProcess", ProcessFactory)

    process = target.execute_async("worker", args=["arg"], cwd="/tmp")
    assert isinstance(process, QemuAsyncProcess)
    assert process.wait() == 17
    assert events == ["ssh-open", "ssh-close"]


@pytest.mark.parametrize("async_new_connection", [False, True])
def test_qemu_async_connection_option_reaches_the_pytest_target(monkeypatch, async_new_connection):
    from score.itf.compat.plugins import qemu as qemu_plugin

    registered = {}
    parser = SimpleNamespace(
        getgroup=lambda _name: SimpleNamespace(addoption=lambda name, **kwargs: registered.update({name: kwargs}))
    )
    qemu_plugin.pytest_addoption(parser)
    assert registered["--qemu-async-new-connection"]["default"] is False
    assert registered["--qemu-async-new-connection"]["action"] == "store_true"
    config = SimpleNamespace(
        getoption=lambda name: async_new_connection if name == "qemu_async_new_connection" else None
    )
    monkeypatch.setattr(qemu_plugin, "itf_session", lambda config: SimpleNamespace(target=Handle()))
    fixture = qemu_plugin.target_init.__wrapped__(SimpleNamespace(config=config), None)
    target = next(fixture)
    assert target._async_new_connection is async_new_connection
    with pytest.raises(StopIteration):
        next(fixture)


@pytest.mark.parametrize("async_new_connection", [False, True])
def test_legacy_qemu_config_fixture_uses_the_pack_config_model(monkeypatch, async_new_connection):
    from score.itf.compat.plugins import qemu as qemu_plugin

    parsed = object()

    class Config:
        def getoption(self, name):
            return {
                "qemu_config": "qemu.json",
                "qemu_kernel": None,
                "qemu_image": "legacy.ifs",
                "qemu_rootfs": "root.qcow2",
                "qemu_disk": "data.qcow2",
                "qemu_async_new_connection": async_new_connection,
            }[name]

    monkeypatch.setattr(qemu_plugin, "load_configuration", lambda path: parsed if path == "qemu.json" else None)
    value = qemu_plugin._qemu_config(Config())

    assert value.qemu_config is parsed
    assert value.qemu_async_new_connection is async_new_connection
    assert (value.qemu_kernel, value.qemu_rootfs, value.qemu_disk) == ("legacy.ifs", "root.qcow2", "data.qcow2")


def test_legacy_qemu_process_uses_a_session_and_pack_target(monkeypatch, tmp_path):
    from score.itf.compat import qemu as qemu_compat

    class Platform:
        console = "guest-console"
        guest_panicked = False
        active = False

        def running(self):
            return self.active

        def terminate(self):
            self.active = False

        def stop(self):
            self.active = False

    class FakeSession:
        def __init__(self, *, target, **kwargs):
            self.document = yaml.safe_load(target)
            self.target = SimpleNamespace(platform=Platform())
            self.brought_up = 0
            self.reached = []
            self.closed = False
            self.run_dir = kwargs["run_dir"]

        def resolve(self):
            return self

        def bring_up(self):
            self.brought_up += 1
            self.target.platform.active = True

        def reach(self, *states):
            self.reached.append(states)
            self.target.platform.active = True

        def close(self):
            self.closed = True

    made = []
    monkeypatch.setattr(qemu_compat, "Session", lambda **kwargs: made.append(FakeSession(**kwargs)) or made[-1])
    process = qemu_compat.QemuProcess(
        "kernel.ifs", "1G", 2, ["lo"], [], "virt-aarch64", "root.img", "console=tty", "data.qcow2"
    )
    try:
        assert process.start(console_callbacks=[("panic", lambda: None)]) is process
        session = made[0]
        assert session.document["packs"]["qemu"] == "score.itf.packs.qemu.plugin"
        assert session.document["capabilities"]["platform"]["factory"] == "qemu.platform"
        assert session.brought_up == 1
        assert session.target.platform._compat_console_callbacks[0][0] == "panic"
        assert process.console == "guest-console" and process.is_running()
        process.stop()
        assert not process.is_running()
        process.start()
        assert session.reached == [("platform.up",)]
    finally:
        process.close()
    assert session.closed


@pytest.mark.parametrize("async_new_connection", [None, False, True])
def test_qemu_target_context_uses_session_roles_and_closes_it(monkeypatch, async_new_connection):
    from score.itf.compat import qemu as qemu_compat
    from score.itf.packs.qemu.config import Network, QemuConfigModel

    class FakeSession:
        def __init__(self, *, target, **_kwargs):
            self.document = yaml.safe_load(target)
            self.target = Handle(
                platform=SimpleNamespace(guest_panicked=False),
                endpoint=SimpleNamespace(host="127.0.0.1", port=22),
                credentials=SimpleNamespace(user="root", password="", key_path=None),
                shell=object(),
                command=Command(),
                process=object(),
                files=object(),
                ping=object(),
            )
            self.resolved = False
            self.started = False
            self.closed = False

        def resolve(self):
            self.resolved = True

        def bring_up(self):
            self.started = True

        def close(self):
            self.closed = True

    made = []

    def create_session(**kwargs):
        session = FakeSession(**kwargs)
        made.append(session)
        return session

    monkeypatch.setattr(qemu_compat, "Session", create_session)
    config = QemuConfigModel(
        networks=[Network(name="lo", ip_address="127.0.0.1", gateway="127.0.0.1")],
        ssh_port=2222,
        qemu_num_cores=2,
        qemu_ram_size="1G",
    )
    test_config = SimpleNamespace(
        qemu_config=config, qemu_kernel="kernel.ifs", qemu_rootfs="root.img", qemu_disk="disk.img"
    )
    if async_new_connection is not None:
        test_config.qemu_async_new_connection = async_new_connection

    with qemu_compat.qemu_target(test_config) as target:
        session = made[0]
        assert target.has("platform") and target.has("command")
        assert session.document["capabilities"]["platform"]["factory"] == "qemu.platform"
        assert session.resolved and session.started
        assert target._async_new_connection is bool(async_new_connection)

    assert session.closed


@pytest.mark.parametrize("target_file", ["qemu.itf.yaml", "qemu_dlt.itf.yaml"])
def test_legacy_qemu_targets_allow_time_for_emulated_ssh_startup(tmp_path, monkeypatch, target_file):
    monkeypatch.setenv("LEGACY_QEMU_CONFIG", str(tmp_path / "qemu.json"))
    session = ItfSession(
        target=Path(legacy.__file__).parent / "targets" / target_file,
        plan_only=True,
        artifacts="none",
    ).resolve()
    try:
        shell = next(node for node in session._target_plan.nodes if node.name == "shell")
        assert dict(shell.config).get("n_retries", 5) == 60
        assert dict(shell.config).get("retry_interval", 1.0) == 2.0
    finally:
        session.close()


def test_qemu_restart_keeps_the_roles_and_reconnects_the_session(tmp_path, monkeypatch):
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

        assert all(session.target.get(name) is before[name] for name in roles)
        assert session.target.shell.is_connected()
        assert session.target.states() >= {"platform.up", "shell.open", "network.reachable"}
        assert events == ["start", "connect", "disconnect", "stop", "start", "connect"]
    finally:
        session.close()


@pytest.mark.parametrize("dlt", [False, True])
@pytest.mark.parametrize("ssh", [False, True])
def test_docker_file_role_selects_the_configured_transport(monkeypatch, ssh, dlt):
    monkeypatch.setenv("LEGACY_DOCKER_IMAGE", "unused:latest")
    monkeypatch.setenv("LEGACY_SSH_USER", "tester")
    monkeypatch.setenv("LEGACY_SSH_PASSWORD", "password")
    target_file = f"docker{'_ssh' if ssh else ''}{'_dlt' if dlt else ''}.itf.yaml"
    session = ItfSession(
        target=Path(legacy.__file__).parent / "targets" / target_file,
        plan_only=True,
        artifacts="none",
    ).resolve()
    try:
        files = next(node for node in session._target_plan.nodes if node.name == "files")
        assert files.provider == ("ssh.files" if ssh else "docker.files")
        assert not session.target.has("sftp")
        if ssh:
            shell = next(node for node in session._target_plan.nodes if node.name == "shell")
            assert dict(shell.config)["n_retries"] == 30
    finally:
        session.close()


@pytest.mark.parametrize("command,process,files", product(("docker", "ssh"), repeat=3))
def test_custom_docker_ssh_target_can_mix_role_transports(monkeypatch, command, process, files):
    monkeypatch.setenv("LEGACY_DOCKER_IMAGE", "unused:latest")
    monkeypatch.setenv("LEGACY_SSH_USER", "tester")
    monkeypatch.setenv("LEGACY_SSH_PASSWORD", "password")
    providers = {"command": f"{command}.exec", "process": f"{process}.process", "files": f"{files}.files"}
    session = ItfSession(
        target=Path(legacy.__file__).parent / "targets" / "docker_ssh.itf.yaml",
        overrides=[yaml.safe_dump({"capabilities": providers, "goals": ["platform.up", "shell.open"]})],
        plan_only=True,
        artifacts="none",
    ).resolve()
    try:
        nodes = {node.name: node for node in session._target_plan.nodes}
        assert nodes["shell"].provider == "ssh.shell"
        assert all(nodes[name].provider == provider for name, provider in providers.items())
    finally:
        session.close()


def test_docker_ssh_logs_in_with_the_target_files_credentials(monkeypatch):
    from score.itf.compat.legacy import DockerTarget

    seen = {}
    monkeypatch.setattr(legacy, "Ssh", lambda **kwargs: seen.update(kwargs) or "ssh")
    handle = Handle(
        endpoint=SimpleNamespace(host="10.0.0.2", port=2222),
        credentials=SimpleNamespace(user="tester", password="secret", key_path=None),
    )
    target = DockerTarget(handle)

    assert target.ssh() == "ssh"
    assert (seen["username"], seen["password"], seen["port"]) == ("tester", "secret", 2222)
    target.ssh("other", "pw")  # the original positional order still overrides the login
    assert (seen["username"], seen["password"]) == ("other", "pw")


@pytest.mark.parametrize("published,host,port", [(32768, "127.0.0.1", 32768), (None, "172.17.0.5", 2222)])
def test_docker_ssh_without_ssh_roles_connects_to_port_2222_as_the_original(monkeypatch, published, host, port):
    from score.itf.compat.legacy import DockerTarget

    seen = {}
    monkeypatch.setattr(legacy, "Ssh", lambda **kwargs: seen.update(kwargs) or "ssh")
    platform = SimpleNamespace(host_port=lambda key: published if key == "2222/tcp" else None, ip=lambda: "172.17.0.5")
    target = DockerTarget(Handle(platform=platform))

    assert target.ssh() == "ssh"
    assert (seen["target_ip"], seen["port"], seen["username"], seen["password"]) == (host, port, "score", "score")


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


def test_the_compatibility_policy_verifies_sftp_after_target_goals():
    import importlib.util
    from pathlib import Path

    import score.itf.compat

    path = Path(score.itf.compat.__file__).parent / "targets" / "policy.py"
    spec = importlib.util.spec_from_file_location("compat_policy_sftp_under_test", path)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)

    class Sftp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def list_dirs_and_files(self, path):
            assert path == "/"
            return ["home"]

    target = Handle(shell=object(), files=Sftp())
    session = Session(target)
    policy.itf_verify(session)

    assert session.checks == {"sftp.answers": True}

    target.roles["platform"] = SimpleNamespace(running=lambda: False)
    session.checks.clear()
    policy.itf_verify(session)
    assert session.checks == {}
