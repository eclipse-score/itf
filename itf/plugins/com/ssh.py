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
import time
import logging
import paramiko

# Reduce the logging level of paramiko, from DEBUG to INFO
logging.getLogger("paramiko").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


class Ssh:
    def __init__(
        self,
        target_ip,
        port=22,
        timeout=15,
        n_retries=5,
        retry_interval=1,
        pkey_path=None,
        password=None,
    ):
        self._target_ip = target_ip
        self._port = port
        self._timeout = timeout
        self._retries = n_retries
        self._retry_interval = retry_interval
        self._ssh = None
        self._pkey = paramiko.ECDSAKey.from_private_key_file(pkey_path) if pkey_path else None
        self._password = password

    def __enter__(self):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())

        for _ in range(self._retries):
            try:
                self._ssh.connect(
                    hostname=self._target_ip,
                    port=self._port,
                    timeout=self._timeout,
                    username="root",
                    password=self._password,
                    pkey=self._pkey,
                    banner_timeout=200,
                    look_for_keys=False,
                )
                break
            except Exception:
                time.sleep(self._retry_interval)
        else:
            raise Exception(f"ssh connection to {self._target_ip} failed")

        return self._ssh

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._ssh.close()
        logger.info("Closed ssh connection.")


def command_with_etc(command):
    return f"if uname >/dev/null 2>&1; then ({command}); else (if [ -e /etc/profile ]; then (. /etc/profile; {command}); else ({command}); fi;); fi"


def _read_output(stream_type, stream, logger_in, log):
    """Logs the output from a given stream and returns the lines of output.

    :param stream_type: The type of stream to read the output from (stdout or stderr).
    :type stream_type: str
    :param stream: The stream to read the output from (stdout or stderr).
    :type stream: paramiko.ChannelFile
    :param logger_in: The logger object used for logging output. If None, the default logger is used.
    :type logger_in: logging.Logger, optional
    :param log: Boolean to know if to log the output or not
    :type log: bool, optional

    :return: A list of lines read from the stream.
    :rtype: list[str]
    """

    if not logger_in and log:
        logger_in = logging.getLogger()

    lines = []
    recv_ready_method = stream.channel.recv_ready if stream_type == "stdout" else stream.channel.recv_stderr_ready
    if recv_ready_method():
        lines = stream.readlines()
        if log:
            for line in lines:
                logger_in.info(line.strip())

    return lines


def _read_output_with_timeout(stream, logger_in, log, max_exec_time):
    """Logs the output from a given stream and returns the lines of output.

    :param stream: The stream to read the output from (should be stdout).
    :type stream: paramiko.ChannelFile
    :param logger_in: The logger object used for logging output. If None, the default logger is used.
    :type logger_in: logging.Logger, optional
    :param log: Boolean to know if to log the output or not
    :type log: bool, optional
    :param max_exec_time: The maximum time (in seconds) to wait for the read operations to occur.
    :type max_exec_time: int

    :return: A list of lines read from the stream.
    :rtype: list[str]
    """

    if not logger_in and log:
        logger_in = logging.getLogger()

    stream.channel.settimeout(max_exec_time)
    start_time = time.time()
    lines = []
    try:
        while not stream.channel.exit_status_ready() or stream.channel.recv_ready():
            line = stream.readline()
            lines.append(line)
            if log:
                logger_in.info(line.strip())
            elapsed_time = time.time() - start_time
            stream.channel.settimeout(max_exec_time - elapsed_time)
    except Exception as ex:
        return lines, ex
    return lines, ""


def execute_command_merged_output(ssh_connection, cmd, timeout=30, max_exec_time=180, logger_in=None, verbose=True):
    """Executes a command on a remote SSH server and captures the output, with both a start timeout and an execution timeout.

    :param ssh_connection: The SSH connection object used to execute the command.
    :type ssh_connection: paramiko.SSHClient
    :param cmd: The command to be executed on the remote server.
    :type cmd: str
    :param timeout: The maximum time (in seconds) to wait for the command to begin executing. Defaults to 30 seconds.
    :type timeout: int, optional
    :param max_exec_time: The maximum time (in seconds) to wait for the command to complete execution. Defaults to 60 seconds.
    :type max_exec_time: int, optional
    :param logger_in: The logger object used for logging output. If None, the default logger is used. Defaults to None.
    :type logger_in: logging.Logger, optional
    :param verbose: If True, logs the command output. Defaults to True.
    :type verbose: bool, optional

    :return: A tuple containing the exit status, and the merged standard output and standard error lines.
    :rtype: tuple(int, list[str])
    """

    cmd_ipn = command_with_etc(cmd)
    stdin, stdout, stderr = ssh_connection.exec_command(cmd_ipn, timeout=timeout)

    output_lines = []
    stdout.channel.set_combine_stderr(True)
    output_lines, exception = _read_output_with_timeout(stdout, logger_in, verbose, max_exec_time)
    try:
        found_exception = False
        if exception:
            ssh_connection.exec_command(f"pkill -f '{cmd_ipn}'")
            logger.error(f"Command '{cmd}' took more than {max_exec_time} seconds to run, process was killed.")
            found_exception = True
    except Exception as ex:
        logger.error(f"Exception: '{ex}'")
        found_exception = True
    try:
        rvalue = -1 if found_exception else stdout.channel.recv_exit_status()
    except Exception:
        logger.error(f"Could not retrieve exit status of command '{cmd}'.")
        rvalue = -1
    finally:
        if not stdout.channel.closed:
            stdout.channel.close()
        if not stderr.channel.closed:
            stderr.channel.close()
        if not stdin.channel.closed:
            stdin.channel.close()
    return rvalue, output_lines


def execute_command_output(ssh_connection, cmd, timeout=30, max_exec_time=180, logger_in=None, verbose=True):
    """Executes a command on a remote SSH server and captures the output, with both a start timeout and an execution timeout.

    :param ssh_connection: The SSH connection object used to execute the command.
    :type ssh_connection: paramiko.SSHClient
    :param cmd: The command to be executed on the remote server.
    :type cmd: str
    :param timeout: The maximum time (in seconds) to wait for the command to begin executing. Defaults to 30 seconds.
    :type timeout: int, optional
    :param max_exec_time: The maximum time (in seconds) to wait for the command to complete execution. Defaults to 60 seconds.
    :type max_exec_time: int, optional
    :param logger_in: The logger object used for logging output. If None, the default logger is used. Defaults to None.
    :type logger_in: logging.Logger, optional
    :param verbose: If True, logs the command output. Defaults to True.
    :type verbose: bool, optional

    :return: A tuple containing the exit status, the standard output lines, and the standard error lines.
    :rtype: tuple(int, list[str], list[str])
    """

    cmd_ipn = command_with_etc(cmd)
    stdin, stdout, stderr = ssh_connection.exec_command(cmd_ipn, timeout=timeout)

    start_time = time.time()
    stdout_lines = []
    stderr_lines = []

    try:
        while not stdout.channel.exit_status_ready():
            if time.time() - start_time > max_exec_time:
                stdout_lines.extend(_read_output("stdout", stdout, logger_in, verbose))
                stderr_lines.extend(_read_output("stderr", stderr, logger_in, verbose))
                ssh_connection.exec_command(f"pkill -f '{cmd_ipn}'")
                logger.error(f"Command '{cmd}' took more than {max_exec_time} seconds to run, process was killed.")
                return -1, stdout_lines, stderr_lines

            stdout_lines.extend(_read_output("stdout", stdout, logger_in, verbose))
            stderr_lines.extend(_read_output("stderr", stderr, logger_in, verbose))
            time.sleep(0.1)

        stdout_lines.extend(_read_output("stdout", stdout, logger_in, verbose))
        stderr_lines.extend(_read_output("stderr", stderr, logger_in, verbose))

        return stdout.channel.recv_exit_status(), stdout_lines, stderr_lines

    finally:
        if not stdout.channel.closed:
            stdout.channel.close()
        if not stderr.channel.closed:
            stderr.channel.close()
        if not stdin.channel.closed:
            stdin.channel.close()


def execute_command(ssh_connection, cmd, timeout=30, max_exec_time=180, logger_in=None, verbose=True):
    logger.debug(f"Executing command: {cmd}")
    logger.debug(f"timeout: {timeout}; max_exec_time: {max_exec_time}; logger_in: {logger_in}; verbose: {verbose};")
    exit_code, stdout_lines, stderr_lines = execute_command_output(
        ssh_connection, cmd, timeout, max_exec_time, logger_in, verbose
    )
    if exit_code != 0:
        stdout_lines = "\n".join(stdout_lines)
        stderr_lines = "\n".join(stderr_lines)
        logger.debug(f"Exit code was {exit_code}.")
        logger.debug(f"stdout_lines: {stdout_lines}")
        logger.debug(f"stderr_lines: {stderr_lines}")

    return exit_code


# pylint: disable=too-many-locals
def binary_transfer(ssh_connection, binary, destination, buffer_size=4 * 1024, logger_in=None):
    mega_bytes = 1024 * 1024
    if not logger_in:
        logger_in = logging.getLogger()
    cmd = f"dd of={destination} bs=64k"
    cmd_ipn = command_with_etc(cmd)
    stdin, stdout, stderr = ssh_connection.exec_command(cmd_ipn)
    size = os.stat(binary).st_size
    transferred = 0
    peer_address, peer_port = ssh_connection.get_transport().getpeername()
    logger_in.info(f"Transferring {binary} to {destination} over {peer_address}:{peer_port}")
    time_start = time.time()
    with open(binary, "rb") as f:
        data = f.read(buffer_size)
        while data != b"":
            stdin.write(data)
            transferred += len(data)
            if transferred % (mega_bytes * 10) == 0:
                time_end = time.time()
                mbps = transferred / (time_end - time_start) / 1024 / 1024
                logger_in.info(f"{transferred // mega_bytes}/{size // mega_bytes} MB transferred, {mbps:.2f} MB/s")
            data = f.read(buffer_size)
    stdin.close()
    exit_status = stdout.channel.recv_exit_status()
    if exit_status:
        stderr_lines = "\n".join([line.rstrip() for line in stderr.readlines()])
        raise RuntimeError(
            "\n".join([f"Transferring {binary} to {destination} failed", "with stderr output:", stderr_lines])
        )
