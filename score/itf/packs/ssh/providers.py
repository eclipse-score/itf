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
"""SSH providers. The shell is `main`'s `Ssh`, constructed unconnected; `ssh.open` (steps.py) connects it."""

from collections.abc import Iterator
from score.itf.core import capability

from .session import Credentials, Endpoint, ShellConfig, Ssh
from .command import Shell, SshExec
from .process import SshProcess
from .files import Sftp, SftpShell


@capability("exec.shell", label="shell")
def make_session(endpoint: Endpoint, credentials: Credentials, config: ShellConfig) -> Iterator[Ssh]:
    shell = Ssh(
        target_ip=endpoint.host,
        port=endpoint.port,
        pkey_path=credentials.key_path,
        username=credentials.user,
        password=credentials.password or "",
        address=endpoint,  # read again at every connect: a restart can publish the port elsewhere
        **config,
    )
    yield shell
    shell.close()


@capability("exec.command", label="exec")
def make_exec(shell: Shell) -> SshExec:
    return SshExec(shell)


@capability("exec.process", label="process")
def make_process(shell: Shell) -> SshProcess:
    return SshProcess(shell)


@capability("files.transfer", label="files")
def make_files(shell: SftpShell) -> Sftp:
    return Sftp(shell, shell.endpoint.host, shell.endpoint.port)
