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
"""Optional structured event stream and startup header for the ITF pytest adapter."""

from __future__ import annotations

import json
import logging
import platform
import re
import sys
import threading
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from types import ModuleType

import pluggy
import pytest

from ...engine.registry import contributor_of
from ...engine import secrets

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

_session_log = logging.getLogger("itf.pytest")
_session_log.propagate = False
_session_log.setLevel(logging.DEBUG)


def pytest_addoption(parser):
    group = parser.getgroup("itf")
    group.addoption(
        "--itf-log-level",
        action="store",
        default=None,
        dest="itf_log_level",
        type=str.upper,
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="level of structured events in itf-run/events.jsonl (default: DEBUG with --itf-artifacts=full)",
    )


class _RunLogFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds")

    def format(self, record):
        text = super().format(record)
        prefix = f"{self.formatTime(record)} {record.levelname:<7} {record.name}: "
        return text.replace("\n", "\n" + prefix)


class _RunEventHandler(logging.Handler):
    def __init__(self, run_dir):
        super().__init__()
        self.events = (run_dir / "events.jsonl").open("w", encoding="utf-8")
        self.sequence = 0
        self.reporter = None
        self.setFormatter(_RunLogFormatter(LOG_FORMAT))

    def emit(self, record):
        with self.lock:
            if self.reporter is not None and record.name != "pytest.terminal":
                self.reporter.drain()
            self.sequence += 1
            event = {
                "schema_version": 1,
                "sequence": self.sequence,
                "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                event["exception"] = self.formatter.formatException(record.exc_info)
            details = getattr(record, "itf_event", None) or getattr(record, "itf_pytest", None)
            if details is not None:
                event["event"] = details
            self.events.write(secrets.mask(json.dumps(event, ensure_ascii=True, default=str)) + "\n")
            self.events.flush()

    def close(self):
        with self.lock:
            if self.reporter is not None:
                self.reporter.drain()
                self.reporter = None
            self.events.close()
            super().close()


class _ReporterStream:
    def __init__(self, terminal, handler):
        self.terminal = terminal
        self.handler = handler
        self.pending = ""
        self.state = threading.local()

    def write(self, text):
        result = self.terminal.write(text)
        if getattr(self.state, "live_log", False):
            return result
        plain = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text).replace("\r", "\n")
        with self.handler.lock:
            self.pending += plain
            while "\n" in self.pending:
                line, self.pending = self.pending.split("\n", 1)
                self._line(line)
        return result

    def _line(self, text):
        if text.strip():
            record = logging.LogRecord("pytest.terminal", logging.INFO, "", 0, text.rstrip(), (), None)
            self.handler.emit(record)

    def drain(self):
        with self.handler.lock:
            text, self.pending = self.pending, ""
            self._line(text)

    def flush(self):
        self.terminal.flush()
        self.handler.flush()

    def __getattr__(self, name):
        return getattr(self.terminal, name)


def _start_event_stream(config, session) -> None:
    """Record structured events only when full artifacts are requested."""
    if session.artifacts != "full":
        return
    run_dir = Path(session.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    handler = _RunEventHandler(run_dir)
    handler.setLevel(config.getoption("itf_log_level") or "DEBUG")
    root = logging.getLogger()
    config._itf_event_handler = (handler, root.level)
    root.addHandler(handler)
    _session_log.addHandler(handler)
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        writer = reporter._tw
        config._itf_terminal_stream = (writer, writer._file)
        stream = _ReporterStream(writer._file, handler)
        writer._file = handler.reporter = stream
        logging_plugin = config.pluginmanager.get_plugin("logging-plugin")
        live_handler = getattr(logging_plugin, "log_cli_handler", None)
        if live_handler is not None:
            original_emit = live_handler.emit

            def emit_live(record):
                stream.state.live_log = True
                try:
                    original_emit(record)
                finally:
                    stream.state.live_log = False

            config._itf_live_handler = (live_handler, original_emit)
            live_handler.emit = emit_live
    if root.level > handler.level or root.level == logging.NOTSET:
        root.setLevel(handler.level)
    _session_log.info("pytest %s, python %s, rootdir %s", pytest.__version__, sys.version.split()[0], config.rootpath)
    _session_log.info(
        "invocation: pytest %s (cwd %s)", " ".join(config.invocation_params.args), config.invocation_params.dir
    )


def _event_stream_enabled(config) -> bool:
    return getattr(config, "_itf_event_handler", None) is not None


def pytest_unconfigure(config):
    handler, level = getattr(config, "_itf_event_handler", (None, None))
    if handler is None:
        return
    live_handler = getattr(config, "_itf_live_handler", None)
    if live_handler is not None:
        live_handler[0].emit = live_handler[1]
        config._itf_live_handler = None
    terminal = getattr(config, "_itf_terminal_stream", None)
    if terminal is not None:
        writer, original = terminal
        writer._file = original
        config._itf_terminal_stream = None
    root = logging.getLogger()
    root.removeHandler(handler)
    _session_log.removeHandler(handler)
    root.setLevel(level)
    handler.close()
    config._itf_event_handler = None


def pytest_runtest_logstart(nodeid, location):
    if _session_log.handlers:
        _session_log.info("START %s", nodeid, extra={"itf_pytest": {"kind": "test_started", "nodeid": nodeid}})


def pytest_runtest_logreport(report):
    if not _session_log.handlers:
        return
    if report.when == "call" or report.outcome != "passed":
        level = logging.ERROR if report.failed else logging.INFO
        _session_log.log(
            level,
            "%s %s (%s, %.3fs)",
            report.outcome.upper(),
            report.nodeid,
            report.when,
            report.duration,
            extra={
                "itf_pytest": {
                    "kind": "test_report",
                    "nodeid": report.nodeid,
                    "phase": report.when,
                    "outcome": report.outcome,
                    "duration": report.duration,
                }
            },
        )
    if report.failed or report.skipped:
        _session_log.log(logging.ERROR if report.failed else logging.INFO, "%s", report.longreprtext)
    for title, content in report.sections:
        if content.strip() and not title.startswith("Captured log"):
            _session_log.info("%s %s:\n%s", title, report.nodeid, content.rstrip())


def pytest_warning_recorded(warning_message, when, nodeid, location):
    if _session_log.handlers:
        _session_log.warning(
            "%s%s: %s", f"{nodeid}: " if nodeid else "", warning_message.category.__name__, warning_message.message
        )


def _emit_itf_header(config, contributors, session) -> None:
    distributions = metadata.packages_distributions()

    def versions(package):
        names = distributions.get(package, ())
        if package == "score":
            names = ("score-itf",)
        installed = []
        for name in sorted(names):
            try:
                installed.append(f"{name}=={metadata.version(name)}")
            except metadata.PackageNotFoundError:
                continue
        return ", ".join(installed) or "source"

    roots = {contributor_of(module.__name__) for module, origin in contributors if origin == "plugin"}
    modules = [
        module
        for module in config.pluginmanager.get_plugins()
        if isinstance(module, ModuleType) and contributor_of(module.__name__) in roots
    ]
    forwarded = set()
    for module in modules:
        plugins = getattr(module, "pytest_plugins", ())
        forwarded.update([plugins] if isinstance(plugins, str) else plugins)
    lines = [
        f"core: {versions('score')}",
        f"runtime: Python {platform.python_version()}, {platform.system()} {platform.machine()}, "
        f"pytest {pytest.__version__}, pluggy {pluggy.__version__}",
        "adapter: score.itf.core.adapters.pytest.plugin",
        f"mode: {'plan-only' if session.plan_only else 'execute'}, reuse={session.reuse}, "
        f"on_exit={session.on_exit}, gating={session.gating}",
        f"artifacts: {session.run_dir}",
    ]
    if session.target_source is not None:
        lines.append(f"target file: {session.target_source.describe()}")
    lines += [f"override: {source.describe()}" for source in session.override_sources]
    for module, origin in sorted(contributors, key=lambda item: item[0].__name__):
        if origin == "policy":
            lines.append(f"policy: {getattr(module, '__file__', module.__name__)}")
    # Packs the target file names load when the session resolves, and are logged then ("pack <name> <version>");
    # listed here are only the pytest plugins of packs that implement an ITF hook.
    if roots:
        lines.append("pytest plugins with ITF hooks (pack / version / entrypoints):")
    for root in sorted(roots):
        entrypoints = sorted(
            module.__name__
            for module in modules
            if contributor_of(module.__name__) == root and module.__name__ not in forwarded
        )
        lines.append(f"  {root} / {versions(root)} / {', '.join(entrypoints)}")
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        _session_log.info("ITF session\n%s", "\n".join(lines))
    else:
        reporter.write_sep("=", "ITF session")
        for line in lines:
            reporter.write_line(line)
        reporter.write_sep("=")


@pytest.hookimpl
def pytest_itf_session_created(config, session, contributors):
    _start_event_stream(config, session)
    _emit_itf_header(config, contributors, session)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    if _event_stream_enabled(session.config):
        _session_log.info(
            "collected %d item(s):%s", len(session.items), "".join(f"\n  {item.nodeid}" for item in session.items)
        )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    yield
    if _event_stream_enabled(session.config):
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        stats = getattr(reporter, "stats", {})
        counts = ", ".join(f"{len(stats[key])} {key}" for key in sorted(stats) if key and stats[key])
        _session_log.info("session finished: exit status %s (%s)", int(exitstatus), counts or "nothing run")
