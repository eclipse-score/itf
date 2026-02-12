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
import json
import logging
from types import SimpleNamespace


logger = logging.getLogger(__name__)


def _dict_to_obj(data):
    """
    Recursively convert a dictionary to an object with attributes.
    Lists of dictionaries are converted to lists of objects.
    """
    if isinstance(data, dict):
        return SimpleNamespace(**{key: _dict_to_obj(value) for key, value in data.items()})
    elif isinstance(data, list):
        return [_dict_to_obj(item) for item in data]
    else:
        return data


def load_configuration(config_file: str):
    """
    Load the configuration from a JSON file.
    param config_file: The path to the configuration file.
    """
    logger.info(f"Loading configuration from {config_file}")
    with open(config_file, "r") as f:
        config_data = json.load(f)
        return _dict_to_obj(config_data)
