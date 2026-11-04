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
"""Paramiko plumbing shared by the providers: connecting with retries and reading a command's output
with both a start timeout and an execution timeout (carried over from ITF's `Ssh` class)."""

from __future__ import annotations

import logging
import select
import shlex
import time

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:  # the SDK loads only when a part runs, never for a plan
    import paramiko

logger = logging.getLogger(__name__)


def load_private_key(key_path: str) -> paramiko.PKey:
    import paramiko

    key_types = (paramiko.RSAKey, paramiko.ECDSAKey, paramiko.Ed25519Key)
    errors = []
    for key_type in key_types:
        try:
            return key_type.from_private_key_file(key_path)
        except Exception as exc:
            errors.append(f"{key_type.__name__}: {exc}")
    raise paramiko.SSHException(
        f"Unsupported or invalid private key file '{key_path}'. "
        f"Tried key types: {', '.join(k.__name__ for k in key_types)}. Details: {' | '.join(errors)}"
    )


def connect(
    host: str,
    port: int,
    user: str,
    *,
    password: str | None = None,
    key_path: str | None = None,
    timeout: float = 15.0,
    n_retries: int = 5,
    retry_interval: float = 1.0,
    keep_alive_interval: int | None = None,
) -> paramiko.SSHClient:
    """An open client, after up to `n_retries` attempts; raises ConnectionError naming the endpoint."""
    import paramiko

    pkey = load_private_key(key_path) if key_path else None
    last_error: Exception | None = None
    for _ in range(max(1, n_retries)):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                pkey=pkey,
                timeout=timeout,
                banner_timeout=200,
                look_for_keys=False,
                allow_agent=False,
            )
        except Exception as exc:
            last_error = exc
            logger.debug("SSH connection to %s:%s failed: %s", host, port, exc)
            client.close()
            time.sleep(retry_interval)
            continue
        if keep_alive_interval is not None and client.get_transport() is not None:
            client.get_transport().set_keepalive(keep_alive_interval)
        logger.info("SSH connection to %s:%s established", host, port)
        return client
    raise ConnectionError(f"could not SSH to {host}:{port} after {n_retries} attempt(s)") from last_error


def login_shell(command: str) -> str:
    """Run `command` in a login shell, sourcing /etc/profile when present (PATH on QNX and Yocto)."""
    inner = f"[ -r /etc/profile ] && . /etc/profile >/dev/null 2>&1; {command}"
    return f"sh -lc {shlex.quote(inner)}"


def execute_command_output(
    client: paramiko.SSHClient,
    command: str,
    *,
    timeout: float = 30.0,
    max_exec_time: float = 180.0,
    logger_in: logging.Logger | None = None,
    log: bool = True,
    separate_stderr: bool = True,
    raw_output: bool = False,
) -> tuple[int, list[str] | bytes, list[str] | bytes]:
    """Return captured output; exit code -1 if it ran longer than `max_exec_time`."""
    logger_in = logger_in or logger
    logger_in.debug("Executing command: %s", command)
    _, stdout, _ = client.exec_command(login_shell(command), timeout=timeout)
    stdout_lines, stderr_lines, exception = _read_output_with_timeout(
        stdout, logger_in, log, max_exec_time, separate_stderr=separate_stderr, raw_output=raw_output
    )
    try:
        if exception:
            logger_in.error("Command '%s' did not finish within %s seconds", command, max_exec_time)
            return -1, stdout_lines, stderr_lines
        return stdout.channel.recv_exit_status(), stdout_lines, stderr_lines
    finally:
        if not stdout.channel.closed:
            stdout.channel.close()


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


def _read_output_with_timeout(
    stream, logger_in, log, max_exec_time, separate_stderr: bool = False, raw_output: bool = False
):
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

    :return: Captured stdout, stderr, and exception. Output is bytes when `raw_output` is True;
        otherwise it is returned as lines. If no exception occurred, exception is an empty string.
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
    stdout_bytes = []
    stderr_bytes = []
    stdout_partial = ""
    stderr_partial = ""

    def collect(data: bytes, is_stderr: bool = False) -> None:
        nonlocal stdout_partial, stderr_partial
        if is_stderr:
            new_lines, stderr_partial = _iter_channel_lines_from_bytes(data, stderr_partial)
            stderr_lines.extend(new_lines)
            if raw_output:
                stderr_bytes.append(data)
        else:
            new_lines, stdout_partial = _iter_channel_lines_from_bytes(data, stdout_partial)
            stdout_lines.extend(new_lines)
            if raw_output:
                stdout_bytes.append(data)
        if log:
            for line in new_lines:
                logger_in.info(line.rstrip("\n"))

    try:
        while True:
            now = time.time()
            if now > deadline:
                raise TimeoutError(f"Command did not finish within {max_exec_time} seconds")

            did_read = False

            if channel.recv_ready():
                data = channel.recv(32768)
                collect(data)
                did_read = True

            if separate_stderr and channel.recv_stderr_ready():
                data = channel.recv_stderr(32768)
                collect(data, is_stderr=True)
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
                        collect(data)
                        drained = True

                if separate_stderr and channel.recv_stderr_ready():
                    data = channel.recv_stderr(32768)
                    if data:
                        collect(data, is_stderr=True)
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
        if raw_output:
            return b"".join(stdout_bytes), b"".join(stderr_bytes), ex
        if stdout_partial:
            stdout_lines.append(stdout_partial)
        if stderr_partial:
            stderr_lines.append(stderr_partial)
        return stdout_lines, stderr_lines, ex

    if raw_output:
        return b"".join(stdout_bytes), b"".join(stderr_bytes), ""
    if stdout_partial:
        stdout_lines.append(stdout_partial)
    if stderr_partial:
        stderr_lines.append(stderr_partial)
    return stdout_lines, stderr_lines, ""
