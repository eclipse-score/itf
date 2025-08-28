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
import os
import stat
import logging
from itf.plugins.com.ssh import Ssh, execute_command

# Reduce the logging level of paramiko, from DEBUG to INFO
logging.getLogger("paramiko").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


class Sftp:
    def __init__(self, ssh, target_ip, port=22):
        if not ssh:
            self._new_ssh = True
        else:
            self._new_ssh = False
        self._ssh = ssh or Ssh(target_ip=target_ip, port=port)
        self._sftp = None

    def __enter__(self):
        """
        Open sftp connection to target given an ssh connection
        """
        if self._new_ssh:
            self._ssh = self._ssh.__enter__()
        self._sftp = self._ssh.open_sftp()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._sftp.close()
        if self._new_ssh:
            self._ssh.close()
            logger.info("Closed ssh connection.")

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

    def download(self, remote_path, local_path, verbose=True):
        if verbose:
            logger.debug(f"Downloading '{remote_path}' to '{local_path}'")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self._sftp.get(remote_path, local_path)
        remote_stat = self._sftp.stat(remote_path)
        os.utime(local_path, (remote_stat.st_atime, remote_stat.st_mtime))

    def upload(self, local_path, remote_path, verbose=True):
        if verbose:
            logger.debug(f"Uploading '{local_path}' to '{remote_path}'")
        if not os.path.exists(local_path):
            logger.error(f"Missing file '{local_path}' while trying to upload")
        remote_dir = os.path.dirname(remote_path)
        assert (
            execute_command(self._ssh, f"test -d {remote_dir} || mkdir -p {remote_dir}") == 0
        ), f"Could not create remote path: {os.path.dirname(remote_path)}"
        self._sftp.put(local_path, remote_path)

    def list_dirs_and_files(self, remote_path):
        return self._sftp.listdir_attr(remote_path)

    def list_dirs_and_files_name(self, remote_path):
        return self._sftp.listdir(remote_path)

    def get_directory_size(self, remote_path):
        total_size = 0
        for file_name in self._sftp.listdir(remote_path):
            stat_info = self._sftp.stat(remote_path + file_name)
            total_size += stat_info.st_size
        return total_size

    def make_directory(self, remote_path):
        self._sftp.mkdir(remote_path)

    def stat(self, remote_path):
        return self._sftp.stat(remote_path)

    def file_exists(self, remote_path):
        try:
            return self._sftp.stat(remote_path) is not None
        except FileNotFoundError:
            return False

    def remove(self, path):
        try:
            logger.debug(f"Removing '{path}'")
            self._sftp.remove(path)
        except EnvironmentError as exc:
            raise EnvironmentError(f'SFTP failed. Remote path "{path}".') from exc

    def get_directory_size_excluding_files(self, remote_path, exclude_file_list):
        total_size = 0
        for file_name in self._sftp.listdir(remote_path):
            if file_name not in exclude_file_list:
                stat_info = self._sftp.stat(remote_path + file_name)
                total_size += stat_info.st_size
        return total_size

    def get_file_size(self, remote_path, file_name):
        file_size = 0
        for remote_file_name in self._sftp.listdir(remote_path):
            if remote_file_name == file_name:
                stat_info = self._sftp.stat(remote_path + file_name)
                file_size += stat_info.st_size
                break
        return file_size

    def rmdir(self, remote_path):
        self._sftp.rmdir(remote_path)

    def upload_dir(self, local_path, remote_path, verbose=True):
        for dirpath, _, filenames in os.walk(local_path):
            dirpath_relative = os.path.relpath(dirpath, local_path)
            for filename in filenames:
                self.upload(
                    os.path.join(dirpath, filename), os.path.join(remote_path, dirpath_relative, filename), verbose
                )

    def download_dir(self, remote_path, local_path, verbose=True):
        for dirpath, filenames in self.walk(remote_path):
            relative_dirpath = os.path.relpath(dirpath, remote_path)
            for filename in filenames:
                self.download(
                    os.path.join(dirpath, filename), os.path.join(local_path, relative_dirpath, filename), verbose
                )
