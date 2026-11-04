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
"""What the packs publish and expect, read from their declarations: the shape of a factory is its return
annotation, so these fail when a class stops naming a member consumers rely on."""

import pytest

from score.itf.contracts import inventory


@pytest.fixture(scope="module")
def contracts():
    packs = inventory.known_packs()
    catalog, errors = inventory.load_catalog(packs)
    assert errors == []
    data = inventory.inventory(catalog, errors=errors, packs=packs)
    return {c["contract"]: c for c in data["contracts"]}


def offered(contracts, contract):
    return {o["label"]: set(o["shape"]) for o in contracts[contract]["offered_by"]}


def test_every_log_stream_offers_is_active(contracts):
    shapes = offered(contracts, "observe.logs")
    assert set(shapes) >= {"dlt.receive", "dlt.receive_tcp", "sim.logs"}
    assert [label for label, shape in shapes.items() if "is_active" not in shape] == []


def test_every_action_making_logs_active_expects_is_active(contracts):
    needers = contracts["observe.logs"]["needed_by"]
    assert {n["label"] for n in needers} >= {"dlt.start_receive", "sim.subscribe"}
    assert [n["label"] for n in needers if "is_active" not in n["expects"]] == []


@pytest.mark.parametrize(
    "contract, label, members",
    [
        ("diagnostics.core_dump", "core_dump.collector", {"collect"}),
        ("net.ping", "ping.pinger", {"host", "ping", "wait_up", "wait_down"}),
        ("descriptor.endpoint", "docker.endpoint", {"host", "port"}),
        ("descriptor.endpoint", "qemu.endpoint", {"host", "port"}),
        ("descriptor.credentials", "qemu.credentials", {"user", "password", "key_path"}),
        (
            "observe.logs",
            "dlt.receive_tcp",
            {"subscribe", "close", "is_active", "path", "record", "lines", "filter", "window"},
        ),
    ],
)
def test_a_factory_without_gives_still_names_what_it_offers(contracts, contract, label, members):
    assert members <= offered(contracts, contract)[label]


@pytest.mark.parametrize("with_files", [True, False])
def test_core_dump_collector_is_planned_from_its_command_and_files_slots(tmp_path, with_files):
    from score.itf.core import Session
    from score.itf.core.session import ResolutionFailed

    roles = {
        "platform": "localhost.platform",
        "command": "localhost.exec",
        "core_dumps": "core_dump.collector",
    }
    if with_files:
        roles["files"] = "localhost.files"
    session = Session(target={"capabilities": roles}, plan_only=True, run_dir=tmp_path, artifacts="none")
    if with_files:
        session.resolve()
        assert "core_dump.collector" in {node.provider for node in session.target_plan.nodes}
    else:
        with pytest.raises(ResolutionFailed, match="files.transfer"):
            session.resolve()
