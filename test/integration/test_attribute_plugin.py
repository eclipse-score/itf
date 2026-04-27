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

"""
Example test demonstrating the use of @add_test_properties decorator.

This test shows how to add custom properties to test cases that will appear
in the JUnit XML report, including requirement verification information and
test classification metadata.
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from attribute_plugin import add_test_properties


@add_test_properties(
    fully_verifies=["REQ-001", "REQ-002"],
    test_type="requirements-based",
    derivation_technique="requirements-analysis",
)
def test_example_with_properties(request):
    """
    Example test case with custom properties.

    This test demonstrates the @add_test_properties decorator which adds
    custom metadata to the XML test report.
    """
    assert True


def pytest_sessionfinish(session, exitstatus):
    """
    Hook that runs after all tests complete and XML is written.

    This validates that the XML report contains the expected properties
    from the @add_test_properties decorator.
    """
    xml_output_file = os.environ.get("XML_OUTPUT_FILE")
    xml_path = Path(xml_output_file)

    assert xml_path.exists(), f"XML report not found at {xml_path}"

    # Parse the XML file
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Find the test case
    testcase = root.find(".//testcase[@name='test_example_with_properties']")
    assert testcase is not None, "test_example_with_properties not found in XML"

    # Find and validate properties
    properties = testcase.find("properties")
    assert properties is not None, "No properties element found in testcase"

    # Extract properties into a dictionary
    props_dict = {}
    for prop in properties.findall("property"):
        props_dict[prop.get("name")] = prop.get("value")

    # Validate expected properties with clear assertions
    assert "fully_verifies" in props_dict, "fully_verifies property not found"
    assert props_dict["fully_verifies"] == "['REQ-001', 'REQ-002']", (
        f"fully_verifies: expected ['REQ-001', 'REQ-002'], got {props_dict['fully_verifies']}"
    )

    assert "test_type" in props_dict, "test_type property not found"
    assert props_dict["test_type"] == "requirements-based", (
        f"test_type: expected 'requirements-based', got {props_dict['test_type']}"
    )

    assert "derivation_technique" in props_dict, "derivation_technique property not found"
    assert props_dict["derivation_technique"] == "requirements-analysis", (
        f"derivation_technique: expected 'requirements-analysis', got {props_dict['derivation_technique']}"
    )
