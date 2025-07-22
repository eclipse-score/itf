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
import logging
import re
import subprocess
import threading
import time

from collections import defaultdict, deque
from contextlib import nullcontext
from datetime import datetime
from queue import Empty
from typing import Optional


class Console:
    def __init__(self, name, reader, writer, print_logger=True, logfile=None):
        """Initializes the Console instance.

        :param str name: Name of the console.
        :param callable reader: Function to read lines from the console.
        :param callable writer: Function to write commands to the console.
        :param bool print_logger: Flag to enable or disable logging to the console. Defaults to True.
        :param str logfile: Path to the log file for logging output. Defaults to None.
        """
        self.name = name
        self.writer = writer
        self.line_reader = LineReader(
            readline_func=reader,
            name=self.name,
            print_logger=print_logger,
            logfile=logfile,
        )
        self.line_reader.start()

    @property
    def print_logger(self):
        return self.line_reader.print_logger

    @print_logger.setter
    def print_logger(self, value):
        self.line_reader.print_logger = value

    def readline(self, block=False, timeout=None):
        if self.line_reader:
            return self.line_reader.get_line(block, timeout)
        return None

    def write(self, command):
        self.writer(command)

    def run_cmd(self, cmd):
        if cmd is not None:
            if callable(cmd):
                cmd()
            else:
                self.write(cmd)

    def run_sh_cmd_output(self, cmd, timeout=30):
        start_time = time.time()

        cmd_finish = "XTF_DONE"

        self.clear_history()
        self.write(f"{cmd} ; echo {cmd_finish}=$?")

        output = []
        while True:
            remaining = start_time - time.time() + timeout

            if remaining <= 0:
                raise Exception("Timed out waiting for command to finish")

            try:
                line = self.readline(block=True, timeout=remaining)
            except Empty as empty:
                raise Exception("Timed out waiting for command to finish") from empty

            if cmd_finish in line and cmd in line:
                continue

            if cmd_finish in line:
                spl = line.split(f"{cmd_finish}=")
                output.append(spl[0])
                retcode = int(spl[1])
                return retcode, ("\n".join(output)).strip()

            output.append(line)

    def add_expr_cbk(self, expr, cbk, regex=False):
        self.line_reader.add_expr_cbk(expr, cbk, regex)

    def _expect(self, cmd, msgs, timeout, regex=False, end_func=any, clear_history=True):
        if clear_history:
            self.clear_history()
        self.run_cmd(cmd)
        if isinstance(msgs, str):
            msgs = [msgs]
        if self.line_reader.read_cond(msgs, timeout, regex, end_func):
            return True
        raise Exception(f"Failed expect {end_func.__name__}: {cmd}: {msgs}")

    def expect_any(self, cmd, msgs, timeout, regex=False, clear_history=True):
        return self._expect(cmd, msgs, timeout, regex, any, clear_history)

    def expect_all(self, cmd, msgs, timeout, regex=False, clear_history=True):
        return self._expect(cmd, msgs, timeout, regex, all, clear_history)

    def mark(self, cmd, msgs, timeout, clear_history=True):
        if clear_history:
            self.clear_history()
        self.run_cmd(cmd)
        time_points = []
        for msg in msgs:
            if self.line_reader.read_until(msg, timeout):
                time_points.append((msg, time.time()))
            else:
                time_points.append((msg, None))
        return time_points

    def clear_history(self):
        self.line_reader.clear_history()


class PipeConsole(Console):
    """Handles interaction with a subprocess through stdin and stdout.

    This class provides an interface for interacting with a subprocess through
    its stdin and stdout streams. It allows sending commands to the subprocess
    and reading its output with configurable timeout and logging options.
    """

    def __init__(
        self,
        name: str,
        process: subprocess.Popen,
        timeout: int = 10,
        linefeed: str = "\n",
        logfile: Optional[str] = None,
        print_logger: bool = True,
    ) -> None:
        """Initializes the PipeConsole instance.

        :param str name: Name of the console.
        :param subprocess.Popen process: The subprocess.Popen instance representing the process.
        :param int timeout: Timeout in seconds for reading from stdout. Defaults to 10.
        :param str linefeed: Linefeed character(s) to use when sending commands. Defaults to '\n'.
        :param Optional[str] logfile: Path to the log file for logging output. Defaults to None.
        :param bool print_logger: Flag to enable or disable logging to the console. Defaults to True.
        """
        self._timeout = timeout
        self._linefeed = linefeed
        self._process = process
        self._logger = logging.getLogger(str(process))

        def reader() -> Optional[str]:
            """Reads a line from the process's stdout with a timeout.

            Continuously checks if the process's stdout is ready for reading
            and reads a line from it. If the read operation times out, it
            returns None. If EOF is detected, it breaks the loop.

            :returns: The decoded line from stdout or None if EOF is detected or a timeout occurs.
            :rtype: Optional[str]
            """
            while True:
                line = self._process.stdout.readline()
                if not line:  # EOF detected
                    break
                if line.endswith(b"\n") or line.endswith(b"# "):
                    return try_to_decode(line)
            self._process.stdout.close()
            return None

        def writer(command: str) -> None:
            """Writes a command to the process's stdin.

            Ensures the command is encoded with the specifiec encoding and
            and appends the specified linefeed character(s) before flushing
            the stdin stream.

            :param str command: The command to be sent to the process's stdin.
            """
            if self._process.poll() is None:
                self._process.stdin.write(try_to_encode(command + "\n"))
                self._process.stdin.flush()

        super().__init__(name, reader, writer)


class LineReader(threading.Thread):
    """
    This class launches a separate thread to read line-by-line
    messages from a specific pipe that blocks, unblocking when
    a new message is ready, or when the pipe is closing,
    returning None. The messages are stored in a queue, and
    can be later retrieved.
    """

    log_locks = {}
    log_queues = {}

    def __init__(self, readline_func, name, print_logger=True, logfile=None):
        """Initializes the LineReader instance.

        :param callable readline_func: Function to read lines from the console.
        :param str name: Name of the console.
        :param bool print_logger: Flag to enable or disable logging to the console. Defaults to True.
        :param str logfile: Path to the log file for logging output. Defaults to None.
        """
        super().__init__(name=name)
        self.readline_func = readline_func
        self.name = name
        self.logger = logging.getLogger(name)
        self.print_logger = print_logger
        self._logfile = logfile
        self._log_queue = LineReaderQueue(max_size=400)
        self._expr_cbks = defaultdict(lambda: [])
        if logfile:
            if logfile not in LineReader.log_locks:
                LineReader.log_locks[logfile] = threading.Lock()
                LineReader.log_queues[logfile] = LineReaderQueue(max_size=400)
            self._log_queue = LineReader.log_queues[logfile]

    def run(self):
        with open(self._logfile, encoding="utf-8", mode="a") if self._logfile else nullcontext() as logfile:
            while True:
                try:
                    line = self.readline_func()
                except Exception:
                    line = None
                if line is None:
                    break
                line = line.replace("\x00", "")
                line = line.strip()
                message = ""
                if line:
                    message = f"[{datetime.now()}] [{self.name}] - {line}"
                if self.print_logger:
                    self.logger.info(line)
                if self._logfile:
                    with LineReader.log_locks[self._logfile]:
                        try:
                            logfile.write(f"{message} \n")
                            logfile.flush()
                            if "SIPDBG_02" in self.name:
                                message = line
                            self._add_log(message)
                        except Exception as exception:
                            self.logger.error(f"Exception on write: {exception}")
                else:
                    self._add_log(line)

                for expr, regex in self._expr_cbks:
                    for cbk in self._expr_cbks[(expr, regex)]:
                        if self._check_msg(line, expr, regex):
                            cbk()

    def add_expr_cbk(self, expr, cbk, regex=False):
        self._expr_cbks[(expr, regex)].append(cbk)

    def read_cond(self, exprs, timeout=90, regex=False, end_func=any):
        start = time.time()
        checks = [False] * len(exprs)
        while True:
            time_remaining = start - time.time() + timeout
            if time_remaining <= 0:
                break
            try:
                line = self.get_line(block=True, timeout=time_remaining)
            except Empty:
                break
            for i, expr in enumerate(exprs):
                if self._check_msg(line, expr, regex):
                    checks[i] = True
            if end_func(checks):
                return True
        return False

    def clear_history(self):
        self._log_queue.clear()

    def read_until(self, expr, timeout=90, regex=False):
        assert isinstance(expr, str)
        return self.read_cond([expr], timeout, regex, any)

    def read_until_one_of(self, exprs, timeout=90, regex=False):
        return self.read_cond(exprs, timeout, regex, any)

    def read_until_all(self, exprs, timeout=90, regex=False):
        return self.read_cond(exprs, timeout, regex, all)

    def read_until_expr(self, expr, timeout=90):
        return self.read_until(expr, timeout, regex=True)

    def read_until_one_of_expr(self, exprs, timeout=90):
        return self.read_until_one_of(exprs, timeout, regex=True)

    def read_until_all_expr(self, exprs, timeout=90):
        return self.read_until_all(exprs, timeout, regex=True)

    def get_line(self, block=False, timeout=None):
        return self._log_queue.get(block=block, timeout=timeout)

    def _add_log(self, log):
        self._log_queue.put(log)

    @staticmethod
    def _check_msg(msg, expr, regex=False):
        return (regex and re.search(expr, msg)) or (not regex and expr in msg)


class LineReaderQueue:
    """
    Thread-safe implementation of a queue.
    When the queue is full, older items
    are removed.
    """

    def __init__(self, max_size=0):
        """Initializes the LineReaderQueue instance.

        :param int max_size: Maximum size of the queue. If set to 0, the queue can grow indefinitely.
        """
        self.queue = deque()
        self.max_size = max_size
        self.mutex = threading.Lock()
        self.not_empty = threading.Condition(self.mutex)

    def put(self, item):
        with self.mutex:
            if self.max_size > 0 and len(self.queue) >= self.max_size:
                self.queue.popleft()
            self.queue.append(item)
            self.not_empty.notify()

    def get(self, block=True, timeout=None):
        with self.not_empty:
            if not block:
                if len(self.queue) == 0:
                    raise Empty
            elif timeout is None:
                while len(self.queue) == 0:
                    self.not_empty.wait()
            elif timeout < 0:
                raise ValueError("'timeout' must be a non-negative number")
            else:
                endtime = time.time() + timeout
                while len(self.queue) == 0:
                    remaining = endtime - time.time()
                    if remaining <= 0.0:
                        raise Empty
                    self.not_empty.wait(remaining)
            item = self.queue.popleft()
            return item

    def clear(self):
        with self.mutex:
            self.queue.clear()


def try_to_encode(data, encoding="ascii"):
    if isinstance(data, str):
        return data.encode(encoding)
    if isinstance(data, bytes):
        return data
    raise TypeError("could not encode data. must be a str or bytes")


def try_to_decode(data, encoding="ascii"):
    if isinstance(data, bytes):
        data = re.sub(b"\r[^\n]", b"", data)
        return data.decode(encoding, "replace").rstrip("\n").rstrip("\r")
    if isinstance(data, str):
        return data.rstrip("\n").rstrip("\r")
    raise TypeError("could not decode data. must be a str or bytes")


def try_to_ascii(data):
    return try_to_encode(data, "ascii")


def try_to_decode_ascii(data):
    return try_to_decode(data, "ascii")
