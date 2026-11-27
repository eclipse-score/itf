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
from stat import S_IFDIR, S_IFREG
from types import SimpleNamespace

import pytest
from unittest.mock import Mock

from score.itf.packs.ssh import client as ssh_client
from score.itf.packs.ssh.command import SshExec
from score.itf.packs.ssh.files import Sftp
from score.itf.packs.ssh.session import Ssh


class FakeChannel:
    def __init__(self, stdout=(), stderr=(), exit_status=0):
        self.stdout = list(stdout)
        self.stderr = list(stderr)
        self.exit_status = exit_status
        self.closed = False
        self.combined_stderr = None

    def set_combine_stderr(self, combine):
        self.combined_stderr = combine
        if combine:
            self.stdout.extend(self.stderr)
            self.stderr.clear()

    def settimeout(self, timeout):
        pass

    def recv_ready(self):
        return bool(self.stdout)

    def recv(self, size):
        return self.stdout.pop(0)

    def recv_stderr_ready(self):
        return bool(self.stderr)

    def recv_stderr(self, size):
        return self.stderr.pop(0)

    def exit_status_ready(self):
        return not self.stdout and not self.stderr

    def recv_exit_status(self):
        return self.exit_status

    def close(self):
        self.closed = True


class FakeSftpClient:
    def __init__(self):
        self.closed = False
        self.timeout = None
        self.entries = [
            SimpleNamespace(filename="folder", st_mode=S_IFDIR),
            SimpleNamespace(filename="file", st_mode=S_IFREG),
        ]

    def get_channel(self):
        return SimpleNamespace(settimeout=lambda timeout: setattr(self, "timeout", timeout))

    def listdir(self, path):
        if path == "/missing":
            raise FileNotFoundError(path)
        return [entry.filename for entry in self.entries]

    def listdir_attr(self, path):
        return self.entries if path == "/" else []

    def stat(self, path):
        if path == "/missing":
            raise FileNotFoundError(path)
        return SimpleNamespace(st_size=3, st_atime=1, st_mtime=1)

    def close(self):
        self.closed = True


class FakeSSHClient:
    def __init__(self, channel=None, sftp=None):
        self.channel = channel
        self.sftp = sftp or FakeSftpClient()
        self.closed = False

    def get_transport(self):
        return SimpleNamespace(is_active=lambda: True, set_keepalive=lambda interval: None)

    def exec_command(self, command, timeout):
        return None, SimpleNamespace(channel=self.channel), None

    def open_sftp(self):
        return self.sftp

    def close(self):
        self.closed = True


class FakeSSHConnection:
    def __init__(self, client):
        self.client = client
        self.entered = 0
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exited += 1

    def get_paramiko_client(self):
        return self.client


@pytest.fixture
def connections(monkeypatch):
    opened = []

    def fake_connect(host, port, user, **kwargs):
        client = FakeSSHClient(channel=FakeChannel([b"\xffout\n"], [b"err\n"], exit_status=5))
        opened.append((host, port, user, kwargs, client))
        return client

    monkeypatch.setattr(ssh_client, "connect", fake_connect)
    monkeypatch.setattr(ssh_client.select, "select", lambda *args: ([], [], []))
    return opened


def test_ssh_keeps_the_original_constructor_and_command_api(connections):
    ssh = Ssh(
        "target",
        port=2202,
        timeout=9,
        keep_alive_interval=12,
        n_retries=3,
        retry_interval=0,
        pkey_path="/tmp/key",
        username="alternate-user",
        password="alternate-password",
    )
    with ssh as entered:
        assert entered is ssh
        assert entered.get_paramiko_client() is connections[0][4]
        assert entered.execute_command_output("cmd") == (5, ["\ufffdout\n"], ["err\n"])
    host, port, user, kwargs, client = connections[0]
    assert (host, port, user) == ("target", 2202, "alternate-user")
    assert kwargs == {
        "password": "alternate-password",
        "key_path": "/tmp/key",
        "timeout": 9,
        "n_retries": 3,
        "retry_interval": 0,
        "keep_alive_interval": 12,
    }
    assert client.closed and not ssh.is_connected()


def test_ssh_exec_uses_its_timeout_and_raises_on_timeout():
    execute_command_output = Mock(return_value=(-1, [], []))
    command = SshExec(SimpleNamespace(execute_command_output=execute_command_output))

    with pytest.raises(TimeoutError, match="within 1 seconds"):
        command.exec("sleep 5", timeout=1)

    execute_command_output.assert_called_once_with("sleep 5", timeout=1, max_exec_time=1, separate_stderr=False)


def test_entering_reuses_a_session_an_action_opened(connections):
    ssh = Ssh("target")
    ssh.connect()
    with ssh as entered:
        assert entered is ssh
    assert ssh.is_connected() and len(connections) == 1


def test_without_reuse_entering_opens_a_separate_connection_to_the_same_endpoint(connections):
    ssh = Ssh("target", port=2202, reuse_session=False)
    ssh.connect()
    with ssh as entered:
        assert entered is not ssh
        assert entered.get_paramiko_client() is connections[1][4]
        assert connections[1][:2] == ("target", 2202)
    assert connections[1][4].closed
    assert ssh.is_connected() and not connections[0][4].closed


def test_command_role_returns_stdout_as_bytes(connections):
    ssh = Ssh("target")
    ssh.connect()
    assert SshExec(ssh).exec("cmd") == (5, "\ufffdout\nerr\n".encode())


@pytest.mark.parametrize(
    ("command", "args", "expected"),
    [
        ("/bin/echo", None, "exec /bin/echo"),
        ("exec /bin/echo", None, "exec /bin/echo"),
        ("FOO=1 /bin/echo", None, "FOO=1 /bin/echo"),
        ("echo ok | cat", None, "echo ok | cat"),
        ("echo first\necho second", None, "echo first\necho second"),
        ("echo 'a;b'", None, "exec echo 'a;b'"),
        (r"echo a\;b", None, r"exec echo a\;b"),
        ('echo prefix"a;b"suffix', None, 'exec echo prefix"a;b"suffix'),
        ('echo "a;b" && echo ok', None, 'echo "a;b" && echo ok'),
        ("/bin/echo", ["a;b", "x|y", "(value)", "<file>"], "exec /bin/echo 'a;b' 'x|y' '(value)' '<file>'"),
    ],
)
def test_ssh_process_executes_simple_commands_without_duplicating_exec(command, args, expected):
    import shlex

    from score.itf.packs.ssh.process import SshProcess

    channel = FakeChannel([b"4", b"2", b"\n"])
    channel.exec_command = Mock()
    shell = SimpleNamespace(
        get_paramiko_client=lambda: SimpleNamespace(get_transport=lambda: SimpleNamespace(open_session=lambda: channel))
    )
    process = SshProcess(shell).spawn(command, args=args)
    process.wait()
    sent = channel.exec_command.call_args.args[0]
    assert shlex.split(sent)[-1].endswith(f"cd / && {expected}")


def test_sftp_borrows_an_open_ssh_and_keeps_its_methods():
    client = FakeSSHClient()
    connection = FakeSSHConnection(client)
    with Sftp(connection, "unused") as sftp:
        assert sftp.list_dirs_and_files_name("/") == ["folder", "file"]
        assert sftp.file_exists("/file") and not sftp.file_exists("/missing")
    assert connection.entered == connection.exited == 0
    assert client.sftp.closed


def test_sftp_without_a_connection_opens_and_closes_its_own(connections):
    with Sftp(None, "target", port=2202, username="user", password="pw") as sftp:
        assert sftp.list_dirs_and_files_name("/") == ["folder", "file"]
    host, port, user, kwargs, client = connections[0]
    assert (host, port, user, kwargs["password"]) == ("target", 2202, "user", "pw")
    assert client.closed


def test_sftp_download_accepts_a_bare_local_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeSftpClient()
    client.get = lambda remote, local: (tmp_path / local).write_bytes(b"downloaded")
    sftp = Sftp(FakeSSHConnection(FakeSSHClient(sftp=client)), "unused")

    sftp.download("/remote/file", "result.txt")

    assert (tmp_path / "result.txt").read_bytes() == b"downloaded"


def test_sftp_upload_quotes_remote_directories_and_rejects_missing_sources(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"contents")
    client = FakeSftpClient()
    client.put = Mock()
    connection = FakeSSHConnection(FakeSSHClient(sftp=client))
    connection.execute_command = Mock(return_value=0)
    sftp = Sftp(connection, "unused")
    remote = "/tmp/a folder's;name/file.txt"

    sftp.upload(str(source), remote)

    import shlex

    connection.execute_command.assert_called_once_with(f"mkdir -p {shlex.quote(remote.rsplit('/', 1)[0])}")
    client.put.assert_called_once_with(str(source), remote)
    with pytest.raises(FileNotFoundError):
        sftp.upload(str(tmp_path / "missing"), remote)


def test_a_session_on_an_endpoint_reconnects_to_where_it_is_now(connections):
    # A container restart can publish the SSH port elsewhere; the endpoint role tells, the session asks it again.
    endpoint = SimpleNamespace(host="127.0.0.1", port=32768)
    ssh = Ssh("127.0.0.1", port=32768, address=endpoint)
    ssh.connect()
    endpoint.port = 32769
    ssh.connect()
    assert [c[:2] for c in connections] == [("127.0.0.1", 32768), ("127.0.0.1", 32769)]
    assert ssh.endpoint.port == 32769
