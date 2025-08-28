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

from itf.plugins.base.target.config.base_processor import BaseProcessor
from itf.plugins.base.target.config.performance_processor import PerformanceProcessor
from itf.plugins.base.target.config.safety_processor import SafetyProcessor
from itf.plugins.base.target.config.ecu import Ecu


logger = logging.getLogger(__name__)

PERFORMANCE_PROCESSORS = {}
SAFETY_PROCESSORS = {}
OTHER_PROCESSORS = {}
ECUS = {}


def load_configuration(config_file: str):
    """
    Load the configuration from a JSON file.
    param config_file: The path to the configuration file.
    """
    logger.info(f"Loading configuration from {config_file}")
    with open(config_file, "r") as file:
        config = json.load(file)
    for ecu_name, ecu_config in config.items():
        performance_processor = None
        if "performance_processor" in ecu_config:
            perf_config = ecu_config.get("performance_processor")
            performance_processor = PerformanceProcessor(
                name=perf_config["name"],
                ip_address=perf_config["ip_address"],
                ssh_port=perf_config["ssh_port"],
                ext_ip_address=perf_config["ext_ip_address"],
                diagnostic_ip_address=perf_config["diagnostic_ip_address"],
                diagnostic_address=int(perf_config["diagnostic_address"], 16),
                serial_device=perf_config["serial_device"],
                network_interfaces=perf_config["network_interfaces"],
                ecu_name=perf_config["ecu_name"],
                data_router_config=perf_config["data_router_config"],
                params=perf_config.get("params", {}),
            )
            PERFORMANCE_PROCESSORS[perf_config["name"]] = performance_processor

        safety_processor = None
        if "safety_processor" in ecu_config:
            safety_config = ecu_config.get("safety_processor")
            safety_processor = SafetyProcessor(
                name=safety_config["name"],
                ip_address=safety_config["ip_address"],
                diagnostic_ip_address=safety_config["diagnostic_ip_address"],
                diagnostic_address=int(safety_config["diagnostic_address"], 16),
                serial_device=safety_config["serial_device"],
                use_doip=safety_config.get("use_doip", False),
                params=safety_config.get("params", {}),
            )
            SAFETY_PROCESSORS[safety_config["name"]] = safety_processor

        other_processors = []
        for other_name, other_config in ecu_config.get("other_processors", {}).items():
            other_processor = BaseProcessor(
                name=other_name,
                ip_address=other_config["ip_address"],
                diagnostic_ip_address=other_config["diagnostic_ip_address"],
                diagnostic_address=int(other_config["diagnostic_address"], 16),
                serial_device=other_config["serial_device"],
                use_doip=other_config.get("use_doip", False),
                params=other_config.get("params", {}),
            )
            OTHER_PROCESSORS[other_name] = other_processor
            other_processors.append(other_processor)

        ECUS[ecu_name] = Ecu(
            name=ecu_name,
            sut=performance_processor,
            sc=safety_processor,
            others=other_processors,
        )


def target_ecu_argparse(ecu: str):
    """
    Convert a string to a TargetECU object.

    param ecu: The string representation of the ECU.
    return: The corresponding TargetECU object.
    raise RuntimeError: If the ECU is not supported.
    """
    try:
        return ECUS[ecu.upper()]
    except KeyError as error:
        raise RuntimeError(f"Unsupported ECU '{ecu}' specified. Supported ECUs are: {ECUS.keys()}") from error
