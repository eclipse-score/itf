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
"""The original target classes over the roles of a composed target.

The original methods map to roles by name, which the compatibility target files (`targets/`) use and a project's
own target file can use too:

| Original | Role |
|---|---|
| `execute` | `command` |
| `execute_async`, `wrap_exec` | `process` |
| `upload`, `download` | `files` |
| `restart` | `platform` |
| `ssh()`, `sftp()`, `ping()`, `ping_lost()` | `endpoint` and `credentials` (a new connection each call, as before) |

Everything else is the target handle's: `target.command`, `target.has("logs")`, `target.reach(...)` work in the
same run, so an old test and a new one can share a target. The original capability names (`exec`,
`file_transfer`, `restart`, `ssh`, `sftp`) follow from the roles present.
"""

from score.itf.core import Facade
from score.itf.packs.ping.ping import ping, ping_lost
from score.itf.packs.ssh.files import Sftp
from score.itf.packs.ssh.session import Ssh
from .target import Target


class LegacyTarget(Target, Facade):
    """The original `Target` as a facade: its methods over the roles below, its capabilities from them."""

    CAPABILITIES = {
        "exec": ("command",),
        "file_transfer": ("files",),
        "restart": ("platform",),
        "ssh": ("endpoint", "credentials"),
        "sftp": ("endpoint", "credentials"),
    }
    REQUIRED_CAPABILITIES = set()  # what the target offers follows from its roles, nothing is assumed

    def __init__(self, handle):
        Facade.__init__(self, handle)
        Target.__init__(self, capabilities=self.capabilities())

    _role = Facade.role

    def execute(self, command: str):
        return self._role("command").exec(command)

    def execute_async(self, binary_path, args=None, cwd="/", **kwargs):
        return self._role("process").spawn(binary_path, args=args, cwd=cwd, **kwargs)

    def upload(self, local_path: str, remote_path: str) -> None:
        self._role("files").upload(local_path, remote_path)

    def download(self, remote_path: str, local_path: str) -> None:
        self._role("files").download(remote_path, local_path)

    def restart(self) -> None:
        self._role("platform").restart()

    def _login(self, username, password, pkey_path) -> dict:
        credentials = self._role("credentials")
        return {
            "username": username or credentials.user,
            "password": password if password is not None else (credentials.password or ""),
            "pkey_path": pkey_path or credentials.key_path,
        }

    def ssh(
        self,
        timeout=15,
        port=None,
        n_retries=5,
        retry_interval=1,
        username=None,
        password=None,
        pkey_path=None,
        ext_ip=False,
    ) -> Ssh:
        """A new SSH connection to the target's endpoint; arguments override the target file's login."""
        endpoint = self._role("endpoint")
        return Ssh(
            target_ip=endpoint.host,
            port=port or endpoint.port,
            timeout=timeout,
            n_retries=n_retries,
            retry_interval=retry_interval,
            **self._login(username, password, pkey_path),
        )

    def sftp(self, ssh_connection=None, username=None, password=None, pkey_path=None) -> Sftp:
        """SFTP over `ssh_connection`, else over a new connection to the target's endpoint."""
        endpoint = self._role("endpoint")
        return Sftp(ssh_connection, endpoint.host, endpoint.port, **self._login(username, password, pkey_path))

    def ping(self, timeout, wait_ms_precision=None):
        return ping(address=self._role("endpoint").host, timeout=timeout, wait_ms_precision=wait_ms_precision)

    def ping_lost(self, timeout, interval=1, wait_ms_precision=None):
        return ping_lost(
            address=self._role("endpoint").host, timeout=timeout, interval=interval, wait_ms_precision=wait_ms_precision
        )


class DockerTarget(LegacyTarget):
    """The original docker target: also `container`, `get_ip`, `get_gateway`, and the container's own attributes."""

    @property
    def container(self):
        return self._role("platform").container

    @property
    def network(self):
        return self._role("platform").network

    def execute(self, command: str):
        from docker.models.containers import ExecResult

        return ExecResult(*super().execute(command))

    def __getattr__(self, name):
        try:
            return super().__getattr__(name)
        except AttributeError:
            if name.startswith("__"):
                raise
            return getattr(self.container, name)

    def get_ip(self, network=None):
        return self._role("platform").ip(network)

    def get_gateway(self, network=None):
        return self._role("platform").gateway(network)

    def ssh(self, username=None, password=None, port=None, **kwargs) -> Ssh:
        """The original positional order; the login defaults to the target file's (`score`/`score` unless set).
        Without SSH roles (no --docker-ssh), as the original: container port 2222, `score`/`score`, reached as
        `docker.endpoint` reaches it (the published host port when there is one, else the container's IP)."""
        if not self.handle.has("endpoint"):
            from score.itf.packs.docker.endpoint import DockerEndpoint

            endpoint = DockerEndpoint(self._role("platform"), {"port": port or 2222})
            return Ssh(
                target_ip=endpoint.host,
                port=endpoint.port,
                username=username or "score",
                password="score" if password is None else password,
                **kwargs,
            )
        return super().ssh(username=username, password=password, port=port, **kwargs)


class QemuTarget(LegacyTarget):
    """The original QEMU target: also `kill_process` and `restart_process`."""

    def __init__(self, handle, *, async_new_connection=False):
        super().__init__(handle)
        self._async_new_connection = async_new_connection

    @property
    def guest_panicked(self) -> bool:
        return self._role("platform").guest_panicked

    def restart(self) -> None:
        """Power-cycle the same machine, as before: its disk and every role are kept, the SSH session reconnects."""
        platform = self._role("platform")
        if self.handle.has("shell"):
            self.handle.get("shell").close()  # a dead peer may not reset the connection; don't wait to find out
        platform.restart()
        self.handle.reach()

    def kill_process(self):
        self._role("platform").stop()

    def execute_async(self, binary_path, args=None, cwd="/", **kwargs):
        if not self._async_new_connection:
            return super().execute_async(binary_path, args=args, cwd=cwd, **kwargs)
        from .qemu import start_qemu_async_process

        return start_qemu_async_process(self, binary_path, args=args, cwd=cwd, **kwargs)

    def restart_process(self):
        self.restart()
