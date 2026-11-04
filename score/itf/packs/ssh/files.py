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
"""`main`'s `Sftp` helper over an `Ssh` (`ssh.files`)."""

import os
import stat
import logging
from functools import wraps
from typing import Protocol

from typing import Optional

from .session import Ssh


class Endpoint(Protocol):
    __contract__ = "descriptor.endpoint"

    host: str
    port: int


class SftpShell(Protocol):
    __contract__ = "exec.shell"

    endpoint: Endpoint

    def execute_command(self, cmd: str, timeout: float = 30) -> int: ...
    def get_paramiko_client(self): ...


logger = logging.getLogger(__name__)


def _with_sftp(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if self._sftp is not None:
            return method(self, *args, **kwargs)
        with self:
            return method(self, *args, **kwargs)

    return wrapped


class Sftp:
    def __init__(
        self,
        ssh: Ssh,
        target_ip: str,
        port: int = 22,
        timeout: int = 15,
        channel_timeout: Optional[float] = None,
        keep_alive_interval: Optional[int] = None,
        n_retries: int = 5,
        retry_interval: int = 1,
        pkey_path: Optional[str] = None,
        username: str = "root",
        password: str = "",
    ):
        """
        Initialize SFTP connection to target with given ssh connection or parameters to create new ssh connection.
        :param Ssh ssh: Existing SSH connection
        :param str target_ip: The IP address of the target SSH server.
        :param int port: The port number of the target SSH server. Default is 22.
        :param int timeout: The timeout duration (in seconds) for the SSH connection. Default is 15 seconds.
        :param Optional[float] channel_timeout: The timeout duration (in seconds) for the SFTP channel. Default is None.
        :param Optional[int] keep_alive_interval: The interval (in seconds) for sending keep-alive messages for
         the SSH connection. Default is None.
        :param int n_retries: The number of retries to attempt for the SSH connection. Default is 5 retries.
        :param int retry_interval: The interval (in seconds) between retries. Default is 1 second.
        :param Optional[str] pkey_path: The file path to the private key for authentication. Default is None.
        :param str username: The username for SSH authentication. Default is "root".
        :param str password: The password for SSH authentication. Default is an empty string.
        """
        if not ssh:
            self._new_ssh = True
        else:
            self._new_ssh = False
        self._channel_timeout = channel_timeout
        self._ssh = ssh or Ssh(
            target_ip=target_ip,
            port=port,
            timeout=timeout,
            keep_alive_interval=keep_alive_interval,
            n_retries=n_retries,
            retry_interval=retry_interval,
            pkey_path=pkey_path,
            username=username,
            password=password,
        )
        self._sftp = None

    def __enter__(self):
        """
        Open sftp connection to target given an SSH connection
        """
        if self._new_ssh:
            self._ssh = self._ssh.__enter__()
        self._sftp = self._ssh.get_paramiko_client().open_sftp()
        if self._channel_timeout is not None:
            self._sftp.get_channel().settimeout(self._channel_timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._new_ssh:
            self._ssh.__exit__(exc_type, exc_val, exc_tb)
            logger.info("Closed SSH connection.")

    def walk(self, remote_path):
        """
        Generate path to all files in directory
        """
        path = remote_path
        files = []
        folders = []
        for f in sorted(self._sftp.listdir_attr(remote_path), key=lambda x: x.filename):
            if stat.S_ISDIR(f.st_mode):
                folders.append(f.filename)
            else:
                files.append(f.filename)
        if files:
            yield path, files

        for folder in folders:
            new_path = os.path.join(remote_path, folder)
            for res in self.walk(new_path):
                yield res

    @_with_sftp
    def download(self, remote_path, local_path, verbose=True):
        if verbose:
            logger.debug(f"Downloading '{remote_path}' to '{local_path}'")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self._sftp.get(remote_path, local_path)
        remote_stat = self._sftp.stat(remote_path)
        os.utime(local_path, (remote_stat.st_atime, remote_stat.st_mtime))

    @_with_sftp
    def upload(self, local_path, remote_path, verbose=True):
        if verbose:
            logger.debug(f"Uploading '{local_path}' to '{remote_path}'")
        if not os.path.exists(local_path):
            logger.error(f"Missing file '{local_path}' while trying to upload")
        remote_dir = os.path.dirname(remote_path)
        assert self._ssh.execute_command(f"test -d {remote_dir} || mkdir -p {remote_dir}") == 0, (
            f"Could not create remote path: {os.path.dirname(remote_path)}"
        )
        self._sftp.put(local_path, remote_path)

    @_with_sftp
    def list_dirs_and_files(self, remote_path):
        return self._sftp.listdir_attr(remote_path)

    @_with_sftp
    def list_dirs_and_files_name(self, remote_path):
        return self._sftp.listdir(remote_path)

    @_with_sftp
    def get_directory_size(self, remote_path):
        total_size = 0
        for file_name in self._sftp.listdir(remote_path):
            stat_info = self._sftp.stat(remote_path + file_name)
            total_size += stat_info.st_size
        return total_size

    @_with_sftp
    def make_directory(self, remote_path):
        self._sftp.mkdir(remote_path)

    @_with_sftp
    def stat(self, remote_path):
        return self._sftp.stat(remote_path)

    @_with_sftp
    def file_exists(self, remote_path):
        try:
            return self._sftp.stat(remote_path) is not None
        except FileNotFoundError:
            return False

    @_with_sftp
    def remove(self, path):
        try:
            logger.debug(f"Removing '{path}'")
            self._sftp.remove(path)
        except EnvironmentError as exc:
            raise EnvironmentError(f'SFTP failed. Remote path "{path}".') from exc

    @_with_sftp
    def get_directory_size_excluding_files(self, remote_path, exclude_file_list):
        total_size = 0
        for file_name in self._sftp.listdir(remote_path):
            if file_name not in exclude_file_list:
                stat_info = self._sftp.stat(remote_path + file_name)
                total_size += stat_info.st_size
        return total_size

    @_with_sftp
    def get_file_size(self, remote_path, file_name):
        file_size = 0
        for remote_file_name in self._sftp.listdir(remote_path):
            if remote_file_name == file_name:
                stat_info = self._sftp.stat(remote_path + file_name)
                file_size += stat_info.st_size
                break
        return file_size

    @_with_sftp
    def rmdir(self, remote_path):
        self._sftp.rmdir(remote_path)

    @_with_sftp
    def upload_dir(self, local_path, remote_path, verbose=True):
        for dirpath, _, filenames in os.walk(local_path):
            dirpath_relative = os.path.relpath(dirpath, local_path)
            for filename in filenames:
                self.upload(
                    os.path.join(dirpath, filename), os.path.join(remote_path, dirpath_relative, filename), verbose
                )

    @_with_sftp
    def download_dir(self, remote_path, local_path, verbose=True):
        for dirpath, filenames in self.walk(remote_path):
            relative_dirpath = os.path.relpath(dirpath, remote_path)
            for filename in filenames:
                self.download(
                    os.path.join(dirpath, filename), os.path.join(local_path, relative_dirpath, filename), verbose
                )

    def exists(self, remote_path: str) -> bool:
        return self.file_exists(remote_path)

    def listdir(self, remote_path: str) -> list[str]:
        return sorted(self.list_dirs_and_files_name(remote_path))
