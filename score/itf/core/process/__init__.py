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
"""Process handling shared by the core and every pack: asynchronous handles on a target
(:class:`AsyncProcess`, :class:`WrappedProcess`) and host-side subprocesses (:class:`ProcessWrapper`,
:class:`PipeConsole`)."""

from .async_process import AsyncProcess
from .console import Console, PipeConsole
from .process_wrapper import ProcessWrapper
from .wrapped_process import WrappedProcess

__all__ = ["AsyncProcess", "Console", "PipeConsole", "ProcessWrapper", "WrappedProcess"]
