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

def py_itf_plugin(py_library, enabled_plugins, args, data, data_as_exec, tags):
    return struct(
        py_library = py_library,
        enabled_plugins = enabled_plugins,
        args = args,
        data = data,
        data_as_exec = data_as_exec,
        tags = tags,
    )
