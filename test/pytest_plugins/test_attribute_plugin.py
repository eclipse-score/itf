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
"""score_tooling's attribute plugin works under py_itf_test: `@add_test_properties` puts properties on the test
case in the JUnit report.

The example runs in a pytest session of its own, writing its report to a temporary directory: its sample
requirement ids (REQ-001, REQ-002) must not reach this test's own report, where the documentation build would look
for those requirements.
"""

import xml.etree.ElementTree as ET

EXAMPLE = '''
from attribute_plugin import add_test_properties


@add_test_properties(
    fully_verifies=["REQ-001", "REQ-002"],
    test_type="requirements-based",
    derivation_technique="requirements-analysis",
)
def test_example_with_properties():
    """An example: the plugin requires a description."""
    assert True
'''


def test_the_properties_reach_the_junit_report(pytester, tmp_path):
    pytester.makepyfile(test_example=EXAMPLE)
    report = tmp_path / "report.xml"
    result = pytester.runpytest("-p", "attribute_plugin", f"--junitxml={report}")
    assert result.ret == 0, result.stdout.str()[-3000:]
    case = ET.parse(report).getroot().find(".//testcase[@name='test_example_with_properties']")
    properties = {p.get("name"): p.get("value") for p in case.find("properties").findall("property")}
    assert properties["FullyVerifies"] == "REQ-001, REQ-002"
    assert properties["TestType"] == "requirements-based"
    assert properties["DerivationTechnique"] == "requirements-analysis"
