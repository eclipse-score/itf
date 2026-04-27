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
import time
import logging
import paramiko
import shlex
import select

# Reduce the logging level of paramiko, from DEBUG to INFO
logging.getLogger("paramiko").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


class Ssh:
    def __init__(
        self,
        target_ip: str,
        port: int = 22,
        timeout: int = 15,
        n_retries: int = 5,
        retry_interval: int = 1,
        pkey_path: str = None,
        username: str = "root",
        password: str = "",
    ):
        """
        Initialize SSH connection to the target.

        :param str target_ip: The IP address of the target SSH server.
        :param int port: The port number of the target SSH server. Default is 22.
        :param int timeout: The timeout duration (in seconds) for the SSH connection. Default is 15 seconds.
        :param int n_retries: The number of retries to attempt for the SSH connection. Default is 5 retries.
        :param int retry_interval: The interval (in seconds) between retries. Default is 1 second.
        :param str pkey_path: The file path to the private key for authentication. Default is None.
        :param str username: The username for SSH authentication. Default is "root".
        :param str password: The password for SSH authentication. Default is an empty string.
        """
        self._target_ip = target_ip
        self._port = port
        self._timeout = timeout
        self._retries = n_retries
        self._retry_interval = retry_interval
        self._username = username
        self._password = password
        self._ssh = None
        self._pkey = self._load_private_key(pkey_path) if pkey_path else None

    @staticmethod
    def _load_private_key(pkey_path: str):
        key_loaders = [
            paramiko.RSAKey,
            paramiko.ECDSAKey,
            paramiko.Ed25519Key,
            paramiko.DSSKey,
        ]

        load_errors = []
        for key_loader in key_loaders:
            try:
                return key_loader.from_private_key_file(pkey_path)
            except Exception as ex:
                load_errors.append(f"{key_loader.__name__}: {ex}")

        raise paramiko.SSHException(
            f"Unsupported or invalid private key file '{pkey_path}'. "
            f"Tried key types: {', '.join(key.__name__ for key in key_loaders)}. "
            f"Details: {' | '.join(load_errors)}"
        )

    def __enter__(self):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())

        logger.info(f"Connecting to {self._target_ip} ...")

        for _ in range(self._retries):
            try:
                self._ssh.connect(
                    hostname=self._target_ip,
                    port=self._port,
                    timeout=self._timeout,
                    username=self._username,
                    password=self._password,
                    pkey=self._pkey,
                    banner_timeout=200,
                    look_for_keys=False,
                )
                logger.info(f"SSH connection to {self._target_ip} established")
                break
            except Exception as ex:
                logger.debug(f"SSH connection to {self._target_ip} failed with error: \n{ex}")
                time.sleep(self._retry_interval)
        else:
            raise Exception(f"SSH connection to {self._target_ip} failed")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._ssh is not None:
            try:
                self._ssh.close()
            finally:
                logger.info("Closed SSH connection.")

    def get_paramiko_client(self):
        return self._ssh

    def execute_command_output(
        self,
        cmd,
        timeout=30,
        max_exec_time=180,
        logger_in=None,
        verbose=True,
        separate_stderr=True,
    ):
        """Executes a command on a remote SSH server and captures the output, with both a start timeout and an execution timeout.

        :param cmd: The command to be executed on the remote server.
        :type cmd: str
        :param timeout: The maximum time (in seconds) to wait for the command to begin executing. Defaults to 30 seconds.
        :type timeout: int, optional
        :param max_exec_time: The maximum time (in seconds) to wait for the command to complete execution. Defaults to 180 seconds.
        :type max_exec_time: int, optional
        :param logger_in: The logger object used for logging output. If None, the default logger is used. Defaults to None.
        :type logger_in: logging.Logger, optional
        :param verbose: If True, logs the command output. Defaults to True.
        :type verbose: bool, optional
        :param separate_stderr: If True, stderr is captured separately. If False, stderr is merged into stdout.
            Defaults to True.
        :type separate_stderr: bool, optional

        :return: A tuple containing the exit status, the standard output lines, and the standard error lines.
            When separate_stderr is False, stderr lines are merged into stdout and the stderr list is empty.
        :rtype: tuple(int, list[str], list[str])
        """

        def command_with_etc(cmd: str) -> str:
            # Source if present, ignore errors, then run the original command
            inner = f"[ -r /etc/profile ] && . /etc/profile >/dev/null 2>&1; {cmd}"
            return f"sh -lc {shlex.quote(inner)}"

        cmd_ipn = command_with_etc(cmd)
        _, stdout, _ = self._ssh.exec_command(cmd_ipn, timeout=timeout)

        stdout_lines, stderr_lines, exception = _read_output_with_timeout(
            stdout,
            logger_in,
            verbose,
            max_exec_time,
            separate_stderr=separate_stderr,
        )

        try:
            if exception:
                logger.error(f"Command '{cmd}' did not finish within {max_exec_time} seconds")
                return -1, stdout_lines, stderr_lines
            return stdout.channel.recv_exit_status(), stdout_lines, stderr_lines
        finally:
            channel = stdout.channel
            if not channel.closed:
                channel.close()

    def execute_command(self, cmd, timeout=30, max_exec_time=180, logger_in=None, verbose=True):
        logger.debug(f"Executing command: {cmd}")
        logger.debug(f"timeout: {timeout}; max_exec_time: {max_exec_time}; logger_in: {logger_in}; verbose: {verbose};")

        exit_code, stdout_lines, stderr_lines = self.execute_command_output(
            cmd, timeout, max_exec_time, logger_in, verbose
        )

        if exit_code != 0:
            stdout_lines = "\n".join(stdout_lines)
            stderr_lines = "\n".join(stderr_lines)
            logger.debug(f"Exit code was {exit_code}.")
            logger.debug(f"stdout_lines: {stdout_lines}")
            logger.debug(f"stderr_lines: {stderr_lines}")

        return exit_code


def _iter_channel_lines_from_bytes(
    data: bytes,
    partial: str,
    encoding: str = "utf-8",
    errors: str = "replace",
):
    text = partial + data.decode(encoding, errors=errors)
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        partial = lines.pop()
    else:
        partial = ""
    return lines, partial


def _read_output_with_timeout(stream, logger_in, log, max_exec_time, separate_stderr: bool = False):
    """Logs the output from a given stream and returns the lines of output.

    :param stream: The stream to read the output from (should be stdout).
    :type stream: paramiko.ChannelFile
    :param logger_in: The logger object used for logging output. If None, the default logger is used.
    :type logger_in: logging.Logger, optional
    :param log: Boolean to know if to log the output or not
    :type log: bool, optional
    :param max_exec_time: The maximum time (in seconds) to wait for the read operations to occur.
    :type max_exec_time: int

    :param separate_stderr: If True, also captures stderr separately (via the underlying Channel).
    :type separate_stderr: bool

    :return: A tuple of (stdout_lines, stderr_lines, exception). If separate_stderr is False,
        stderr_lines will be an empty list. If no exception occurred, exception will be an empty string.
    :rtype: tuple(list[str], list[str], Exception | str)
    """

    if not logger_in and log:
        logger_in = logging.getLogger()

    channel = stream.channel

    # Ensure the channel is configured consistently with the requested capture mode.
    # - separate_stderr=False: merge stderr into stdout
    # - separate_stderr=True: keep stderr separate
    channel.set_combine_stderr(not separate_stderr)

    start_time = time.time()
    deadline = start_time + max_exec_time
    channel.settimeout(0.5)

    stdout_lines = []
    stderr_lines = []
    stdout_partial = ""
    stderr_partial = ""
    try:
        while True:
            now = time.time()
            if now > deadline:
                raise TimeoutError(f"Command did not finish within {max_exec_time} seconds")

            did_read = False

            if channel.recv_ready():
                data = channel.recv(32768)
                new_lines, stdout_partial = _iter_channel_lines_from_bytes(data, stdout_partial)
                stdout_lines.extend(new_lines)
                if log:
                    for line in new_lines:
                        logger_in.info(line.rstrip("\n"))
                did_read = True

            if separate_stderr and channel.recv_stderr_ready():
                data = channel.recv_stderr(32768)
                new_lines, stderr_partial = _iter_channel_lines_from_bytes(data, stderr_partial)
                stderr_lines.extend(new_lines)
                if log:
                    for line in new_lines:
                        logger_in.info(line.rstrip("\n"))
                did_read = True

            if did_read:
                continue

            if channel.exit_status_ready():
                # The remote process has exited, but output may still be buffered
                # in the SSH transport.  Keep draining until recv() returns empty
                # bytes (true EOF) to avoid truncating large outputs.
                remaining = deadline - now
                wait_after_exit = 0 if remaining <= 0 else min(0.5, remaining)
                try:
                    select.select([channel], [], [], wait_after_exit)
                except Exception:
                    time.sleep(min(0.05, remaining if remaining > 0 else 0))

                drained = False
                if channel.recv_ready():
                    data = channel.recv(32768)
                    if data:
                        new_lines, stdout_partial = _iter_channel_lines_from_bytes(data, stdout_partial)
                        stdout_lines.extend(new_lines)
                        if log:
                            for line in new_lines:
                                logger_in.info(line.rstrip("\n"))
                        drained = True

                if separate_stderr and channel.recv_stderr_ready():
                    data = channel.recv_stderr(32768)
                    if data:
                        new_lines, stderr_partial = _iter_channel_lines_from_bytes(data, stderr_partial)
                        stderr_lines.extend(new_lines)
                        if log:
                            for line in new_lines:
                                logger_in.info(line.rstrip("\n"))
                        drained = True

                if drained:
                    continue
                break

            # Avoid busy-waiting. Paramiko Channel supports fileno() on POSIX, so we can
            # use select() to wait for activity up to a small slice of the remaining time.
            remaining = deadline - now
            if remaining <= 0:
                continue
            wait = min(0.5, remaining)
            try:
                select.select([channel], [], [], wait)
            except Exception:
                # Fallback: channel may not be selectable on some platforms.
                time.sleep(min(0.05, remaining))
    except Exception as ex:
        if stdout_partial:
            stdout_lines.append(stdout_partial)
        if stderr_partial:
            stderr_lines.append(stderr_partial)
        return stdout_lines, stderr_lines, ex

    if stdout_partial:
        stdout_lines.append(stdout_partial)
    if stderr_partial:
        stderr_lines.append(stderr_partial)
    return stdout_lines, stderr_lines, ""
