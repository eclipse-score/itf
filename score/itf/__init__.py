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
"""ITF: `import score.itf as itf` is the public API of `score.itf.core`: the same names, the same `Session`.

A run that wants a plan to warn about deprecated contracts hands the session its definitions
(`Session(..., definitions=score.itf.core.adapters.definitions.definitions())`); the pytest adapter and the
command line do. A session needs none.
"""

from .core import *  # noqa: F401,F403
from .core import __all__  # noqa: F401
