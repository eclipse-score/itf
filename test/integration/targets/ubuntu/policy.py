"""Ubuntu's serial login, readiness checks and console evidence."""

import os
import re
from pathlib import Path
from typing import Protocol

from score.itf.core import hookimpl, state


class Console(Protocol):
    __contract__ = "exec.console"

    def is_open(self) -> bool: ...
    def write(self, text: str) -> None: ...
    def mark(self) -> int: ...
    def lines(self, since: int = 0) -> list[str]: ...
    def wait_for(
        self, pattern: str, timeout: float = 30, *, since: int | None = None, regex: bool = False
    ) -> str | None: ...
    def run(self, command: str, timeout: float = 30) -> tuple[int, str]: ...


itf_expect = [Console]

_PROMPT = r"(?P<prompt>login:|#)(?:\s|\x1b\[[0-?]*[ -/]*[@-~])*$"


def _prompt(console: Console) -> str | None:
    if not console.is_open():
        return None
    for _attempt in range(5):
        cursor = console.mark()
        console.write("")
        line = console.wait_for(_PROMPT, timeout=1, since=cursor, regex=True)
        if line is not None:
            return re.search(_PROMPT, line).group("prompt")
    return None


@state("console.shell", after=("shell.open", "console.open"), label="login_ubuntu_console")
def login_ubuntu_console(console: Console) -> None:
    prompt = _prompt(console)
    if prompt == "login:":
        console.write("root")
    elif prompt != "#":
        raise RuntimeError("Ubuntu serial console did not present a login or root-shell prompt")
    if not ubuntu_console_has_shell(console):
        raise RuntimeError("Ubuntu serial console did not reach a responsive root shell")


@login_ubuntu_console.probe
def ubuntu_console_has_shell(console: Console) -> bool:
    try:
        if _prompt(console) != "#":
            return False
        status, _output = console.run("true", timeout=5)
        return status == 0
    except (TimeoutError, RuntimeError):
        return False


@hookimpl
def itf_verify(session):
    target = session.target
    status, output = target.command.exec("echo -n ready")
    session.check("command.answers", status == 0 and output.strip().endswith(b"ready"))
    session.check("platform.running", target.platform.running())
    session.check("console.shell", ubuntu_console_has_shell(target.console))


@hookimpl
def itf_teardown(session):
    evidence = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", ".")) / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "console.txt").write_text("\n".join(session.target.console.lines()), encoding="utf-8")
