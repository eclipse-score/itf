"""Core-backed adapters for the original QEMU helper APIs."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Any

import yaml

from score.itf.core import Session
from score.itf.packs.ssh.process import SshAsyncProcess


def _mapping(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("qemu_config must be a mapping or a Pydantic model")


def _target_document(config_file: str, kernel=None, rootfs=None, disk=None, *, include_roles=False) -> str:
    config = json.loads(Path(config_file).read_text(encoding="utf-8"))
    packs = {"qemu": "score.itf.packs.qemu.plugin"} if kernel or rootfs else {}
    packs.update({"ssh": "score.itf.packs.ssh.plugin", "ping": "score.itf.packs.ping.plugin"})
    capabilities = {}
    goals = []
    if kernel or rootfs:
        capabilities["platform"] = {
            "factory": "qemu.platform",
            "with": {"config_file": config_file, "kernel": kernel, "rootfs": rootfs, "disk": disk},
        }
        capabilities["endpoint"] = "qemu.endpoint"
        capabilities["credentials"] = "qemu.credentials"
        goals.append("platform.up")
        after = "platform.up"
    else:
        packs["net"] = "score.itf.packs.net.plugin"
        endpoint = config["networks"][0]
        auth = config.get("ssh_auth") or {}
        capabilities["endpoint"] = {
            "factory": "net.endpoint",
            "with": {"host": endpoint["ip_address"], "port": config["ssh_port"]},
        }
        if auth.get("pkey_path"):
            capabilities["credentials"] = {
                "factory": "net.key",
                "with": {"user": auth.get("username") or "root", "key_path": auth["pkey_path"]},
            }
        else:
            capabilities["credentials"] = {
                "factory": "net.password",
                "with": {"user": auth.get("username") or "root", "password": auth.get("password") or ""},
            }
        after = "network.reachable"
    if include_roles:
        capabilities.update(
            {
                "shell": "ssh.shell",
                "command": "ssh.exec",
                "process": "ssh.process",
                "files": "ssh.files",
                "ping": "ping.pinger",
            }
        )
        goals.extend(["network.reachable", "shell.open"])
        relations = [{"state": "shell.open", "after": [after]}]
    else:
        relations = []
    return yaml.safe_dump(
        {
            "packs": packs,
            "capabilities": capabilities,
            "goals": goals,
            "relations": relations,
        },
        sort_keys=False,
    )


class QemuAsyncProcess(SshAsyncProcess):
    """Legacy process constructor over the SSH pack's asynchronous process."""

    def __init__(self, target, ssh_context, channel, pid, output_thread, output_lines, *, shell=None):
        super().__init__(shell or target.shell, channel, pid, output_thread, output_lines)
        self._legacy_ssh_context = ssh_context
        self._legacy_ssh_closed = False

    def _close_legacy_ssh(self):
        if self._legacy_ssh_closed:
            return
        self._legacy_ssh_closed = True
        try:
            self._legacy_ssh_context.__exit__(None, None, None)
        except Exception:
            pass

    def wait(self, timeout_s: float = 15) -> int:
        result = super().wait(timeout_s)
        self._close_legacy_ssh()
        return result

    def stop(self) -> int:
        result = super().stop()
        self._close_legacy_ssh()
        return result


def start_qemu_async_process(target, binary_path, args=None, cwd="/", **kwargs):
    """Use the SSH pack on a dedicated connection, as the original QEMU target did."""
    from score.itf.packs.ssh.process import SshProcess

    ssh_context = target.ssh(timeout=30, n_retries=5)
    shell = ssh_context.__enter__()
    try:
        process = SshProcess(shell).spawn(binary_path, args=args, cwd=cwd, **kwargs)
    except BaseException:
        ssh_context.__exit__(None, None, None)
        raise
    return QemuAsyncProcess(
        target,
        ssh_context,
        process._channel,
        process.pid(),
        process._output_thread,
        process._output,
        shell=shell,
    )


class QemuProcess:
    """Legacy process facade backed by an ITF Session and the qemu.platform pack."""

    def __init__(
        self,
        path_to_qemu_kernel_image,
        available_ram,
        available_cores,
        network_adapters,
        port_forwarding,
        machine,
        rootfs,
        kernel_cmdline,
        disk,
    ):
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="itf-qemu-compat-")
        directory = Path(self._temporary_directory.name)
        networks = [
            {"name": str(getattr(adapter, "name", adapter)), "ip_address": "127.0.0.1", "gateway": "127.0.0.1"}
            for adapter in (network_adapters or ["lo"])
        ]
        forwarding = [
            item.model_dump(mode="json")
            if hasattr(item, "model_dump")
            else dict(item)
            if isinstance(item, dict)
            else {"host_port": item.host_port, "guest_port": item.guest_port}
            for item in (port_forwarding or [])
        ]
        config = {
            "networks": networks,
            "ssh_port": 22,
            "qemu_num_cores": int(available_cores),
            "qemu_ram_size": str(available_ram),
            "qemu_machine": machine,
            "qemu_kernel_cmdline": kernel_cmdline,
            "port_forwarding": forwarding,
        }
        config_file = directory / "qemu.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        target = _target_document(str(config_file), path_to_qemu_kernel_image, rootfs, disk, include_roles=False)
        self._session = Session(target=target, run_dir=directory / "itf-run", artifacts="none")
        self._platform = None
        self._resolved = False
        self._started = False

    @property
    def console(self):
        return self._platform.console if self._platform is not None else None

    @property
    def guest_panicked(self) -> bool:
        return bool(self._platform and self._platform.guest_panicked)

    def start(self, console_callbacks=None):
        if not self._resolved:
            self._session.resolve()
            self._platform = self._session.target.platform
            self._resolved = True
        self._platform._compat_console_callbacks = list(console_callbacks or [])
        if self._started:
            self._session.reach("platform.up")
        else:
            self._session.bring_up()
            self._started = True
        return self

    def is_running(self) -> bool:
        return bool(self._platform and self._platform.running())

    def terminate(self) -> None:
        if self._platform is not None:
            self._platform.terminate()

    def stop(self) -> None:
        if self._platform is not None and self._platform.running():
            self._platform.stop()

    def restart(self):
        self.stop()
        return self.start()

    def close(self) -> None:
        try:
            self._session.close()
        finally:
            self._temporary_directory.cleanup()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


@contextmanager
def qemu_target(test_config):
    """Legacy QEMU context API, implemented with a core Session and the QEMU/SSH packs."""
    config = _mapping(test_config.qemu_config)
    directory = tempfile.TemporaryDirectory(prefix="itf-qemu-target-compat-")
    session = None
    try:
        config_file = Path(directory.name) / "qemu.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        kernel = getattr(test_config, "qemu_kernel", None)
        rootfs = getattr(test_config, "qemu_rootfs", None)
        disk = getattr(test_config, "qemu_disk", None)
        target = _target_document(str(config_file), kernel, rootfs, disk, include_roles=True)
        session = Session(
            target=target,
            run_dir=Path(directory.name) / "itf-run",
            artifacts="none",
            bring_up_attempts=max(1, int(getattr(test_config, "qemu_boot_attempts", 1))),
        )
        session.resolve()
        session.bring_up()
        from .legacy import QemuTarget

        yield QemuTarget(
            session.target, async_new_connection=bool(getattr(test_config, "qemu_async_new_connection", False))
        )
    finally:
        try:
            if session is not None:
                session.close()
        finally:
            directory.cleanup()


def boot_until_ready(target, max_attempts: int, run_checks) -> None:
    """Preserve the old helper while reboot/reach are performed through the ITF session."""
    for attempt in range(1, max_attempts + 1):
        try:
            run_checks(target)
            return
        except Exception:
            if not target.guest_panicked or attempt == max_attempts:
                raise
            target.restart()


def pre_tests_phase(target):
    """The original QEMU readiness checks, invoked against a Session-backed Target facade."""
    assert target.ping(timeout=10), "Target is not pingable within expected time frame"
    with target.ssh(timeout=5, n_retries=5, retry_interval=2) as ssh:
        result = ssh.execute_command("echo Qnx_S-core!")
    assert result == 0, "Running SSH command on the target failed"
    with target.sftp() as sftp:
        assert sftp.list_dirs_and_files("/"), "Running SFTP command on the target failed"
