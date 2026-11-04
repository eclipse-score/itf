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

project = "Score ITF"
project_url = "https://github.com/eclipse-score/itf"

extensions = [
    "score_sphinx_bundle",
]

# The contract map of ITF's packs is generated from their code (bazel run //score/itf/cli:itf -- contracts map
# --format html --output docs/_generated/catalog.html; //test/packs:catalog_test fails when it is stale) and
# served from the site root.
html_extra_path = ["_generated"]
