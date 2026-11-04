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
"""A Docker client that does not lose early exec output (ported from main's docker plugin).

docker-py reads exec output from the raw socket, but http.client has already pulled everything that arrived
together with the HTTP response headers into its buffered reader. Output produced right after the exec started
(e.g. the first line a command prints) is therefore silently dropped whenever the client reads the reply late.
Reading through the buffered reader keeps that data. See https://github.com/docker/docker-py/issues/3332 and
https://github.com/docker/docker-py/issues/2042; open fixes: docker-py PRs #3333 and #3438. Remove this once the
upstream issues/PRs are resolved.

The SDK loads when a client is made, never for a plan.
"""

from __future__ import annotations

import struct

_STDOUT = 1
_FRAME_HEADER_SIZE = 8


def read_frames(buffered_reader, tty):
    """Yield ``(stream_id, data)`` frames from the exec response body."""
    if tty:
        while True:
            data = buffered_reader.read1(65536)
            if not data:
                return
            yield _STDOUT, data
    while True:
        header = buffered_reader.read(_FRAME_HEADER_SIZE)
        if len(header) < _FRAME_HEADER_SIZE:
            return
        stream_id, size = struct.unpack(">BxxxL", header)
        data = buffered_reader.read(size) if size else b""
        if data:
            yield stream_id, data
        if len(data) < size:
            return


def from_env(timeout: int):
    """`docker.from_env(timeout=...)`, with exec output read without losing early frames."""
    import docker as docker_sdk
    from docker.utils.socket import consume_socket_output, demux_adaptor

    class ExecAPIClient(docker_sdk.APIClient):
        def _read_from_socket(self, response, stream, tty=True, demux=False):
            sock = self._get_raw_response_socket(response)
            self._disable_socket_timeout(sock)
            frames = read_frames(response.raw._fp.fp, tty)
            if demux:
                frames = (demux_adaptor(*frame) for frame in frames)
            else:
                frames = (data for (_, data) in frames)
            if stream:
                return frames
            try:
                return consume_socket_output(frames, demux=demux)
            finally:
                response.close()

    class ExecDockerClient(docker_sdk.DockerClient):
        def __init__(self, *args, **kwargs):  # pylint: disable=super-init-not-called
            self.api = ExecAPIClient(*args, **kwargs)

    return ExecDockerClient.from_env(timeout=timeout)
