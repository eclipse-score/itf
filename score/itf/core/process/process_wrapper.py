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
import atexit
import contextlib
import contextvars
import logging
import os
import signal
import subprocess
import threading
import time
from subprocess import TimeoutExpired

from score.itf.core.process.console import PipeConsole

logger = logging.getLogger(__name__)

# Every process ITF starts on the host goes through ProcessWrapper, and each one is tracked here from start
# to stop. That is what lets ITF promise that nothing outlives a run: the session reaps whatever a test, a
# provider or a crashed teardown left behind, and one SIGTERM handler (Bazel sends SIGTERM on a test timeout)
# stops them all instead of each wrapper replacing the previous wrapper's handler.
# A process also remembers on whose behalf it was started: the owner set while a session runs (see `activate` and
# `owned_by`). A session reaps its own processes, not those of another session in the same interpreter; the exit
# handler and SIGTERM reap everything.
_OWNER: contextvars.ContextVar = contextvars.ContextVar("itf_process_owner", default=None)
_LIVE: list["ProcessWrapper"] = []
_LOCK = threading.Lock()
_PREVIOUS_SIGTERM = None
_HANDLER_INSTALLED = False


def _on_sigterm(signalnum, frame):
    logger.debug("Received signal %s on frame %s: stopping every tracked process", signalnum, frame)
    ProcessWrapper.reap()
    previous = _PREVIOUS_SIGTERM
    _uninstall_handler()
    if callable(previous):
        previous(signalnum, frame)
    else:
        os.kill(os.getpid(), signal.SIGTERM)  # default action: the run ends as it would have


def _install_handler() -> None:
    global _PREVIOUS_SIGTERM, _HANDLER_INSTALLED
    if _HANDLER_INSTALLED:
        return
    try:
        _PREVIOUS_SIGTERM = signal.signal(signal.SIGTERM, _on_sigterm)
        _HANDLER_INSTALLED = True
    except ValueError:  # not the main thread: the atexit reap below still applies
        logger.debug("not the main thread: no SIGTERM handler installed")


def _uninstall_handler() -> None:
    global _HANDLER_INSTALLED
    if _HANDLER_INSTALLED:
        signal.signal(signal.SIGTERM, _PREVIOUS_SIGTERM if _PREVIOUS_SIGTERM is not None else signal.SIG_DFL)
        _HANDLER_INSTALLED = False


class _Tee:
    """Wraps a process's stdout so every line read is also kept (the console only keeps the last lines)."""

    def __init__(self, stream, sink: list):
        self._stream, self._sink = stream, sink

    def readline(self, *args):
        line = self._stream.readline(*args)
        if line:
            self._sink.append(line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line)
        return line

    def __getattr__(self, name):
        return getattr(self._stream, name)


class ProcessWrapper:
    """
    The one way ITF starts a process on the host: tracked, logged, and guaranteed to be stopped.

    Beyond the original (a long-running binary with a console on its output) it covers every other host-side
    need through options instead of separate code: `stdio` hands the process other streams (a terminal, for
    instance) and `keep_output` retains everything it printed. `run` is the synchronous form for short
    commands. A process that is still alive when the session closes, or when Bazel stops the test, is
    terminated.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        binary_path,
        args=None,
        logger_name=None,
        env=None,
        cwd=None,
        monitor_process_startup=False,
        monitor_process_time=10.0,
        stdio=None,
        keep_output=False,
        new_session=True,
        console_callbacks=None,
    ):
        self._process = None
        # (expression, callback) pairs the console watches from its first line (registered before it reads)
        self._console_callbacks = list(console_callbacks or [])
        self._binary_path = binary_path
        self._args = args
        self._logger_name = logger_name if logger_name is not None else os.path.basename(binary_path)
        self._env = env
        self._cwd = cwd
        self._console = None
        self._monitor_process_startup = monitor_process_startup
        self._monitor_process_time = monitor_process_time
        self._stdio = stdio
        self._keep_output = keep_output
        self._new_session = new_session
        self._output: list[str] = []
        self._owner = None

    @property
    def process(self):
        return self._process

    @property
    def pid(self):
        return self._process.pid

    @property
    def description(self) -> str:
        return f"{self._binary_path} (PID {self._process.pid if self._process else '-'})"

    def __enter__(self):
        self.start_process(self._args)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.kill_process()

    def start_process(self, override_args=None):
        cmd_line_args = [self._binary_path]

        if override_args is not None:  # Do not check for "True" to also allow for an empty array
            cmd_line_args.extend(override_args)
        elif self._args:
            cmd_line_args.extend(self._args)

        logger.info(f"Starting process: {' '.join(cmd_line_args)}")
        streams = (
            {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE if self._logger_name else subprocess.DEVNULL}
            | {"stderr": subprocess.STDOUT}
            if self._stdio is None
            else dict(self._stdio)
        )
        self._output = []
        self._owner = _OWNER.get()
        self._process = subprocess.Popen(
            cmd_line_args, start_new_session=self._new_session, env=self._env, cwd=self._cwd, **streams
        )
        with _LOCK:
            _LIVE.append(self)
        _install_handler()

        if self._process.stdout is not None and streams.get("stdout") == subprocess.PIPE and self._stdio is None:
            if self._keep_output:
                self._process.stdout = _Tee(self._process.stdout, self._output)
            self._console = PipeConsole(self._logger_name, self._process, expr_cbks=self._console_callbacks)

        logger.info(f"Process [{self._binary_path}] started with PID: [{self._process.pid}]")
        if self._monitor_process_startup:
            self.monitor_process(self._monitor_process_time)

        return self

    def terminate(self) -> None:
        """Send SIGTERM and return without waiting: safe from the console's own reader thread, where
        `kill_process` (which waits for that thread) would deadlock."""
        if self._process is not None and self._process.poll() is None:
            pgrp = os.getpgid(self._process.pid) if self._new_session else None
            self._signal(pgrp, signal.SIGTERM)

    def kill_process(self):
        return_code = self._process.poll()
        if return_code is not None:
            # Normal when a `with` block outlives its process; only a surprise if the caller expected it running.
            logger.debug(
                f"Process [{self._binary_path}] with PID: [{self._process.pid}] had already terminated, "
                f"with return code: [{return_code}]."
            )
        else:
            try:
                pgrp = os.getpgid(self._process.pid) if self._new_session else None
                try:
                    logger.info(
                        f"Stopping process [{self._binary_path}] with PID: [{self._process.pid}] by sending SIGTERM"
                        + (f" to its PGID: [{pgrp}]" if pgrp else "")
                    )
                    self._signal(pgrp, signal.SIGTERM)
                    self._process.wait(5)
                    logger.info(f"Process [{self._binary_path}] with PID: [{self._process.pid}] stopped")
                except subprocess.TimeoutExpired:
                    logger.info(
                        f"Process [{self._binary_path}] with PID: [{self._process.pid}] could not be stopped with SIGTERM, sending SIGKILL"
                    )
                    self._signal(pgrp, signal.SIGKILL)
                    self._process.wait(5)
                    logger.info(f"Process [{self._binary_path}] with PID: [{self._process.pid}] forcefully killed")
                except OSError:
                    logger.exception(
                        f"Process [{self._binary_path}] with PID: [{self._process.pid}] could not be stopped"
                    )
            except ProcessLookupError:
                logger.warning(
                    f"Process [{self._binary_path}] with PID: [{self._process.pid}] could no longer be found"
                )
            except subprocess.TimeoutExpired:
                logger.error(f"Process [{self._binary_path}] failed to stop within the timeout period")
        self._drain_output()
        self._untrack()

    def _drain_output(self) -> None:
        """Let the console's reader thread hand over what the process printed before it ended, so that when
        stopping returns every line has been logged and kept: a caller that checks the logs right after a
        `with` block must not race the thread."""
        reader = getattr(self._console, "line_reader", None)
        if reader is not None and reader.is_alive() and reader is not threading.current_thread():
            reader.join(timeout=2)

    def _signal(self, pgrp, signalnum) -> None:
        if pgrp is not None:
            os.killpg(pgrp, signalnum)
        else:
            self._process.send_signal(signalnum)

    def _untrack(self) -> None:
        with _LOCK:
            if self in _LIVE:
                _LIVE.remove(self)
            idle = not _LIVE
        if idle:
            _uninstall_handler()

    @staticmethod
    def activate(owner) -> None:
        """From now on, processes started in this context belong to `owner` (a session, from `resolve()` on)."""
        _OWNER.set(owner)

    @staticmethod
    def deactivate(owner) -> None:
        """`owner` no longer is the one processes belong to (a no-op when another one took over meanwhile)."""
        if _OWNER.get() is owner:
            _OWNER.set(None)

    @staticmethod
    @contextlib.contextmanager
    def owned_by(owner):
        """Processes started inside the block belong to `owner`, whatever else is active."""
        token = _OWNER.set(owner)
        try:
            yield
        finally:
            _OWNER.reset(token)

    @classmethod
    def live(cls, owner=None) -> tuple["ProcessWrapper", ...]:
        """The tracked processes that are still running (finished ones are forgotten here); only `owner`'s when
        one is given."""
        with _LOCK:
            running = [w for w in _LIVE if w._process is not None and w._process.poll() is None]
            _LIVE[:] = running
        return tuple(w for w in running if owner is None or w._owner is owner)

    @classmethod
    def reap(cls, owner=None) -> tuple[str, ...]:
        """Stop every tracked process still running (only `owner`'s when one is given: a session closing does not
        touch another session's) and describe each one that had to be stopped."""
        leftovers = cls.live(owner)
        described = []
        for wrapper in reversed(leftovers):  # newest first, like a teardown
            described.append(wrapper.description)
            logger.warning(f"Process {wrapper.description} was still running and is being terminated")
            wrapper.kill_process()
        return tuple(described)

    @classmethod
    def run(cls, binary_path, args=None, *, timeout=None, cwd=None, env=None, input_text=None, text=True):
        """Run a short command to completion: (exit code, stdout, stderr). Raises TimeoutExpired after
        stopping the process. Same tracking and termination guarantees as a long-running process."""
        wrapper = cls(
            binary_path,
            args,
            cwd=cwd,
            env=env,
            stdio={"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )
        wrapper.start_process()
        try:
            data = input_text.encode() if isinstance(input_text, str) else input_text
            out, err = wrapper.process.communicate(data, timeout=timeout)
        except subprocess.TimeoutExpired:
            wrapper.kill_process()
            raise
        finally:
            wrapper._untrack()
        if text:
            out, err = out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")
        return wrapper.process.returncode, out, err

    @property
    def console(self):
        return self._console

    def output(self) -> str:
        """Everything the process printed so far (needs `keep_output=True`)."""
        return "".join(self._output)

    def exit_code(self) -> int | None:
        """The shell convention: killed by signal N is 128 + N; None while running."""
        code = self._process.poll() if self._process is not None else None
        return None if code is None else (128 - code if code < 0 else code)

    def is_running(self):
        if not self._process:
            return False

        # poll() will return the exit code, if set, otherwise None;
        return self._process.poll() is None

    def wait_to_finish(self, timeout):
        try:
            return_code = self._process.wait(timeout)
            if return_code != 0:
                raise RuntimeError(
                    f"Process [{self._binary_path}] with PID: [{self._process.pid}]) finished with "
                    f"error code {return_code}."
                )
            logger.debug(f"Process [{self._binary_path}] with PID: [{self._process.pid}]) finished successfully.")
        except TimeoutExpired as original_exception:
            self.kill_process()
            raise RuntimeError(
                f"Process [{self._binary_path}] with PID: [{self._process.pid}]) didn't finish "
                f"for timeout of {timeout} seconds."
            ) from original_exception

    def monitor_process(self, time_interval):
        logger.info(f"Monitoring Process [{self._binary_path}] with PID: [{self._process.pid}].")
        start_time = time.time()
        while time.time() < start_time + time_interval:
            if not self.is_running():
                raise RuntimeError(
                    f"Process [{self._binary_path}] with PID: [{self._process.pid}] exited during startup"
                )
            time.sleep(1)

    def restart_process(self, extra_args):
        override_args = None
        if extra_args:
            override_args = self._args + extra_args
            logger.info(f"Restarting {self._binary_path} with args: {override_args}")
        self.kill_process()
        self.start_process(override_args)


# A process left over at interpreter exit (a crash between start and stop) is stopped here.
atexit.register(ProcessWrapper.reap)
