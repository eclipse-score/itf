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
"""Compose a target and use it from a plain script, without pytest.

    python run.py [targets/target.itf.yaml]

`Session(target=...)` is the same session pytest and `itf` build: it loads the packs the factory labels name
(`localhost.platform` loads the `local` pack), plans, brings the target up, hands it over as `session.target` and
unwinds on `close()`. `score.itf.Session` also loads the installed contract definitions, so a plan can warn
about a deprecated contract; `score.itf.core.Session` is the bare engine.
"""

import sys
import tempfile
from pathlib import Path

from score.itf import Session

HERE = Path(__file__).resolve().parent


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    target_file = Path(argv[0]) if argv else HERE / "targets" / "target.itf.yaml"
    with tempfile.TemporaryDirectory(prefix="itf-plain-") as run_dir:
        session = Session(target=target_file, run_dir=run_dir)
        session.resolve()  # the plan: nothing is built yet
        try:
            session.bring_up()  # the planned actions run, in order
            code, output = session.target.command.exec("echo hello from a plain script")
            output = output.decode("utf-8", errors="replace")
            print(f"exit {code}: {output.strip()}")
            return 0 if code == 0 and "hello" in output else 1
        finally:
            session.close()  # unwind


if __name__ == "__main__":
    sys.exit(main())
