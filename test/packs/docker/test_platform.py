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
"""The docker platform without a daemon: what it refuses before it asks one for anything."""

import json
import io
import tarfile
from types import SimpleNamespace

import pytest

from score.itf.core import ConfigValidationFailed, Session
from score.itf.core.engine.close import undetachable
from score.itf.packs.docker import exec_client
from score.itf.packs.docker.platform import DockerPlatform, parse_docker_sdk_kwargs, parse_volumes
from score.itf.packs.docker.files import DockerFiles, download


def _archive(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, contents in entries:
            member = tarfile.TarInfo(name)
            if contents is None:
                member.type = tarfile.DIRTYPE
                archive.addfile(member)
            else:
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
    return [buffer.getvalue()]


def test_docker_files_context_keeps_the_provider_and_propagates_errors():
    platform = object()
    files = DockerFiles(platform)

    with files as entered:
        assert entered is files
    error = RuntimeError("transfer failed")
    with pytest.raises(RuntimeError) as caught:
        with files:
            raise error
    assert caught.value is error
    assert files.platform is platform
    with files as entered:
        assert entered is files


def test_upload_reports_destination_directory_failure(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"contents")
    container = SimpleNamespace(exec_run=lambda args: (1, b"permission denied"))
    files = DockerFiles(SimpleNamespace(container=container))

    with pytest.raises(RuntimeError, match="permission denied"):
        files.upload(str(source), "/restricted/output.txt")


def test_download_copies_the_single_file_in_a_docker_archive(tmp_path):
    container = SimpleNamespace(get_archive=lambda _: (_archive([("output.txt", b"contents")]), {}))
    destination = tmp_path / "downloaded.txt"

    download(container, "/output.txt", str(destination))

    assert destination.read_bytes() == b"contents"


def test_download_rejects_a_directory_archive_instead_of_silently_copying_one_file(tmp_path):
    archive = _archive([("logs/", None), ("logs/first.txt", b"first"), ("logs/second.txt", b"second")])
    container = SimpleNamespace(get_archive=lambda _: (archive, {}))
    destination = tmp_path / "downloaded.txt"

    with pytest.raises(IsADirectoryError, match="one regular file"):
        download(container, "/logs", str(destination))

    assert not destination.exists()


def test_a_volume_whose_host_path_is_missing_is_refused_before_the_daemon_is_asked(tmp_path, monkeypatch):
    # A rootful daemon would create the missing path itself, owned by root, where nothing can clean it up.
    platform = DockerPlatform({"image": "ubuntu:24.04", "volumes": f"{tmp_path / 'nowhere'}:/mnt:ro"})
    monkeypatch.setattr(platform, "client", lambda: pytest.fail("the daemon must not be asked"))
    with pytest.raises(FileNotFoundError, match="nowhere"):
        platform.start()


def test_volumes_that_exist_are_passed_on(tmp_path):
    platform = DockerPlatform({"image": "ubuntu:24.04", "volumes": f"{tmp_path}:/mnt:ro"})
    assert platform.volumes == {str(tmp_path): {"bind": "/mnt", "mode": "ro"}}


def test_named_volumes_are_not_treated_as_missing_host_paths():
    assert parse_volumes("itf-data:/data:rw") == {"itf-data": {"bind": "/data", "mode": "rw"}}
    platform = DockerPlatform({"image": "ubuntu:24.04", "volumes": "itf-data:/data:rw"})
    assert platform.volumes["itf-data"]["bind"] == "/data"


def test_existing_relative_volume_paths_are_resolved_as_host_paths(tmp_path, monkeypatch):
    (tmp_path / "fixture.yaml").write_text("target", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert parse_volumes("fixture.yaml:/target:ro") == {
        str(tmp_path / "fixture.yaml"): {"bind": "/target", "mode": "ro"}
    }


def test_docker_run_receives_legacy_capabilities_and_network_options(monkeypatch):
    captured = {}

    class Containers:
        def run(self, *args, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(short_id="abc")

    platform = DockerPlatform(
        {
            "image": "ubuntu:24.04",
            "network_mode": "host",
            "cap_add": "SYS_ADMIN,NET_ADMIN",
            "devices": "/dev/fuse:/dev/fuse:rwm",
        }
    )
    monkeypatch.setattr(platform, "client", lambda: SimpleNamespace(containers=Containers()))
    platform.start()
    assert captured["network_mode"] == "host"
    assert "network" not in captured
    assert captured["cap_add"] == ["SYS_ADMIN", "NET_ADMIN"]
    assert captured["devices"] == ["/dev/fuse:/dev/fuse:rwm"]


@pytest.mark.parametrize(
    "options", [{"mem_limit": "2g", "userns_mode": "host"}, '{"mem_limit":"2g","userns_mode":"host"}']
)
def test_docker_sdk_kwargs_are_forwarded(monkeypatch, options):
    captured = {}

    class Containers:
        def run(self, *args, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(short_id="abc")

    platform = DockerPlatform({"image": "ubuntu:24.04", "isolated_network": False, "docker_sdk_kwargs": options})
    monkeypatch.setattr(platform, "client", lambda: SimpleNamespace(containers=Containers()))
    platform.start()
    assert captured["mem_limit"] == "2g" and captured["userns_mode"] == "host"
    assert captured["detach"] is True and captured["auto_remove"] is False


@pytest.mark.parametrize(
    "key", ["image", "command", "name", "detach", "auto_remove", "remove", "network", "ports", "volumes", "mounts"]
)
def test_docker_sdk_kwargs_cannot_override_managed_arguments(key):
    with pytest.raises(ValueError, match="cannot override ITF-managed"):
        parse_docker_sdk_kwargs({key: "override"})


@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        "[]",
        "null",
        "false",
        ["mem_limit"],
        {1: "invalid"},
        {"labels": {1: "invalid"}},
        {"extra": object()},
        {"extra": float("nan")},
        '{"extra": Infinity}',
        '{"mem_limit":"256m", "mem_limit":"512m"}',
    ],
)
def test_docker_sdk_kwargs_require_an_explicit_object(value):
    with pytest.raises(ValueError, match="docker_sdk_kwargs"):
        parse_docker_sdk_kwargs(value)


def test_docker_sdk_kwargs_support_nested_values():
    options = {"dns": ["1.1.1.1"], "restart_policy": {"Name": "on-failure", "MaximumRetryCount": 2}}
    assert parse_docker_sdk_kwargs(json.dumps(options)) == options


def test_unknown_sdk_keyword_is_left_to_the_sdk_instead_of_a_local_allowlist():
    assert parse_docker_sdk_kwargs({"future_sdk_option": 42}) == {"future_sdk_option": 42}


def test_docker_sdk_kwargs_do_not_share_mutable_nested_input():
    options = {"dns": ["1.1.1.1"], "restart_policy": {"Name": "on-failure"}}
    normalized = parse_docker_sdk_kwargs(options)
    normalized["dns"].append("8.8.8.8")
    normalized["restart_policy"]["Name"] = "no"
    assert options == {"dns": ["1.1.1.1"], "restart_policy": {"Name": "on-failure"}}


def test_docker_sdk_kwargs_survive_planning_without_contacting_docker(monkeypatch, tmp_path):
    options = {"mem_limit": "256m", "security_opt": ["no-new-privileges:true"]}
    document = {
        "packs": {"docker": "score.itf.packs.docker.plugin"},
        "capabilities": {
            "platform": {
                "factory": "docker.platform",
                "with": {"image": "unused:latest", "docker_sdk_kwargs": json.dumps(options)},
            }
        },
    }
    monkeypatch.setattr(DockerPlatform, "client", lambda self: pytest.fail("must not contact Docker"))
    session = Session(target=json.dumps(document), plan_only=True, run_dir=tmp_path, artifacts="none").resolve()
    try:
        assert session.target.platform.docker_sdk_kwargs == options
    finally:
        session.close()


def test_unknown_top_level_docker_setting_is_still_rejected(tmp_path):
    document = {
        "packs": {"docker": "score.itf.packs.docker.plugin"},
        "capabilities": {"platform": {"factory": "docker.platform", "with": {"image": "unused", "mem_limt": "2g"}}},
    }
    with pytest.raises(ConfigValidationFailed):
        Session(target=json.dumps(document), plan_only=True, run_dir=tmp_path, artifacts="none").resolve()


def test_sdk_kwargs_changed_after_construction_are_validated_before_client_use(monkeypatch):
    platform = DockerPlatform({"image": "unused"})
    platform.docker_sdk_kwargs = {"detach": False}
    monkeypatch.setattr(platform, "client", lambda: pytest.fail("must reject overrides before contacting Docker"))
    with pytest.raises(ValueError, match="detach"):
        platform.start()


def test_start_restarts_an_existing_stopped_container_instead_of_reusing_its_name(monkeypatch):
    class StoppedContainer:
        status = "exited"

        def __init__(self):
            self.started = False

        def reload(self):
            pass

        def start(self):
            self.started = True
            self.status = "running"

    container = StoppedContainer()
    platform = DockerPlatform({"image": "ubuntu:24.04"})
    platform.container = container
    monkeypatch.setattr(platform, "client", lambda: pytest.fail("must reuse the stopped container"))

    platform.start()

    assert container.started and container.status == "running"


def test_named_platform_rediscover_and_remove_owned_container_and_network(monkeypatch):
    owner = "org.eclipse.score.itf.platform"
    container = Container(refusals=0)
    container.status = "running"
    container.attrs = {"Config": {"Labels": {owner: "bench"}}}
    container.reload = lambda: None
    network = SimpleNamespace(name="bench_net", attrs={"Labels": {owner: "bench"}}, removed=False)
    network.remove = lambda: setattr(network, "removed", True)
    client = SimpleNamespace(
        containers=SimpleNamespace(get=lambda name: container),
        networks=SimpleNamespace(get=lambda name: network),
    )
    platform = DockerPlatform({"image": "ubuntu:24.04", "name": "bench"})
    monkeypatch.setattr(platform, "client", lambda: client)

    assert platform.running()
    platform.stop()

    assert container.stopped and container.removed and network.removed


def test_named_platform_refuses_a_container_it_does_not_own(monkeypatch):
    container = SimpleNamespace(attrs={"Config": {"Labels": {}}})
    platform = DockerPlatform({"image": "ubuntu:24.04", "name": "bench"})
    monkeypatch.setattr(
        platform, "client", lambda: SimpleNamespace(containers=SimpleNamespace(get=lambda name: container))
    )

    with pytest.raises(ValueError, match="not owned"):
        platform.running()
    assert platform.container is None
    with pytest.raises(RuntimeError, match="discovery failed.*not owned"):
        platform.stop()


def test_named_platform_refuses_an_unowned_network(monkeypatch):
    owner = "org.eclipse.score.itf.platform"
    container = SimpleNamespace(attrs={"Config": {"Labels": {owner: "bench"}}})
    network = SimpleNamespace(attrs={"Labels": {}})
    client = SimpleNamespace(
        containers=SimpleNamespace(get=lambda name: container), networks=SimpleNamespace(get=lambda name: network)
    )
    platform = DockerPlatform({"image": "ubuntu:24.04", "name": "bench"})
    monkeypatch.setattr(platform, "client", lambda: client)

    with pytest.raises(ValueError, match="network.*not owned"):
        platform.running()
    assert platform.container is None and platform._network is None


def test_fresh_session_reports_discovery_failure_during_close(monkeypatch, tmp_path):
    container = SimpleNamespace(attrs={"Config": {"Labels": {}}})
    client = SimpleNamespace(containers=SimpleNamespace(get=lambda name: container))
    monkeypatch.setattr(DockerPlatform, "client", lambda self: client)
    target = json.dumps(
        {
            "capabilities": {"platform": {"factory": "docker.platform", "with": {"image": "test", "name": "bench"}}},
            "goals": ["platform.up"],
        }
    )
    session = Session(target=target, run_dir=tmp_path, artifacts="none").resolve()
    assert not session.probe()
    session.close()
    assert "not owned" in session.close_problems().render()


def test_named_platform_keep_and_fresh_session_down(monkeypatch, tmp_path):
    docker = pytest.importorskip("docker")
    containers, networks = {}, {}

    def get(collection, name):
        if name not in collection:
            raise docker.errors.NotFound(name)
        return collection[name]

    def create_network(name, **options):
        network = SimpleNamespace(name=name, attrs={"Labels": options["labels"]})
        network.remove = lambda: networks.pop(name)
        networks[name] = network
        return network

    def run_container(image, command, **options):
        name = options["name"]
        container = SimpleNamespace(short_id="abc", status="running", attrs={"Config": {"Labels": options["labels"]}})
        container.reload = lambda: None
        container.stop = lambda timeout: setattr(container, "status", "exited")
        container.remove = lambda force: containers.pop(name)
        containers[name] = container
        return container

    client = SimpleNamespace(
        containers=SimpleNamespace(get=lambda name: get(containers, name), run=run_container),
        networks=SimpleNamespace(get=lambda name: get(networks, name), create=create_network),
    )
    monkeypatch.setattr(DockerPlatform, "client", lambda self: client)
    target = json.dumps(
        {
            "capabilities": {
                "platform": {
                    "factory": "docker.platform",
                    "with": {"image": "test", "name": "bench", "docker_sdk_kwargs": '{"labels":{"team":"test"}}'},
                }
            },
            "goals": ["platform.up"],
        }
    )
    first = Session(target=target, on_exit="keep", run_dir=tmp_path / "first", artifacts="none").resolve()
    assert undetachable(first) is None
    first.bring_up()
    first.close()
    assert set(containers) == {"bench"} and set(networks) == {"bench_net"}
    assert containers["bench"].attrs["Config"]["Labels"]["team"] == "test"

    second = Session(target=target, run_dir=tmp_path / "second", artifacts="none").resolve()
    try:
        assert undetachable(second) is None
        assert second.probe()
    finally:
        second.close()
    assert not containers and not networks


def test_unnamed_docker_is_not_detachable(tmp_path):
    target = json.dumps({"capabilities": {"platform": {"factory": "docker.platform", "with": {"image": "test"}}}})
    session = Session(target=target, run_dir=tmp_path, artifacts="none").resolve()
    try:
        assert "docker.platform" in undetachable(session)
    finally:
        session.close()


def test_no_container_engine_is_reported_with_how_to_start_one(monkeypatch):
    docker_sdk = pytest.importorskip("docker")

    def refuse(**_):
        raise docker_sdk.errors.DockerException("Error while fetching server API version")

    # the client the platform makes (exec_client.from_env), refused as the SDK refuses when no engine answers
    monkeypatch.setattr(exec_client, "from_env", refuse)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    with pytest.raises(ConnectionError, match="DOCKER_HOST is not set.*podman.socket"):
        DockerPlatform({"image": "ubuntu:24.04"}).client()


class Container:
    def __init__(self, refusals):
        self.refusals, self.name, self.stopped, self.removed = refusals, "score_itf_x", False, False

    def stop(self, timeout):
        self.stopped = True

    def remove(self, force):
        if self.refusals:
            self.refusals -= 1
            raise RuntimeError("removal of container score_itf_x is already in progress")
        self.removed = True


def test_a_removal_refused_right_after_the_stop_is_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    platform = DockerPlatform({"image": "ubuntu:24.04", "isolated_network": False})
    platform.container = container = Container(refusals=2)
    platform.stop()
    assert container.stopped and container.removed and platform.container is None


def test_network_is_removed_when_container_stop_fails():
    platform = DockerPlatform({"image": "ubuntu:24.04"})
    container = Container(refusals=0)
    network = SimpleNamespace(removed=False)
    network.remove = lambda: setattr(network, "removed", True)
    platform.container = container
    platform._network = network

    def fail_stop(timeout):
        raise RuntimeError("stop failed")

    container.stop = fail_stop
    with pytest.raises(RuntimeError, match="stop failed"):
        platform.stop()
    assert container.removed and network.removed
    assert platform.container is None and platform._network is None


def test_network_is_removed_when_container_removal_fails(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    platform = DockerPlatform({"image": "ubuntu:24.04"})
    container = Container(refusals=5)
    network = SimpleNamespace(removed=False)
    network.remove = lambda: setattr(network, "removed", True)
    platform.container = container
    platform._network = network

    with pytest.raises(RuntimeError, match="removal of container"):
        platform.stop()
    assert container.stopped and not container.removed and network.removed
    assert platform.container is container and platform._network is None
