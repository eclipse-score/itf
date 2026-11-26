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
"""A fake ECU: a UART with a shell behind it, served on a TCP port (default 2323).

Runs inside a container on a stock Python image. Every connection gets its own shell on a
pseudo-terminal, which echoes input like a real console and starts with a boot banner. A test
reaches it from the host with pyserial's `socket://host:port` URL, so the real serial console
provider talks to a device that answers.
"""

import os
import pty
import select
import socket
import sys
import threading

BANNER = "FAKE-ECU 1.0 boot complete"
PORT = int(os.environ.get("FAKE_ECU_PORT", "2323"))


def serve(connection: socket.socket) -> None:
    pid, terminal = pty.fork()
    if pid == 0:  # the child: a banner, then a read-eval loop (no prompt, state persists across commands)
        os.execvp("sh", ["sh", "-c", f'echo "{BANNER}"; while IFS= read -r line; do eval "$line"; done'])
    try:
        while True:
            ready, _, _ = select.select([connection, terminal], [], [])
            if connection in ready:
                data = connection.recv(4096)
                if not data:
                    break
                os.write(terminal, data)
            if terminal in ready:
                try:
                    data = os.read(terminal, 4096)
                except OSError:  # the shell exited
                    break
                if not data:
                    break
                connection.sendall(data)
    finally:
        connection.close()
        os.close(terminal)
        try:
            os.kill(pid, 15)
            os.waitpid(pid, 0)
        except OSError:
            pass


def main() -> None:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen()
    print(f"fake ECU listening on {PORT}", flush=True)
    while True:
        connection, _ = server.accept()
        threading.Thread(target=serve, args=(connection,), daemon=True).start()


if __name__ == "__main__":
    sys.exit(main())
