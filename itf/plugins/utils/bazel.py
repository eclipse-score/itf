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
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def get_output_dir():
    """Prepare the path for the results file, based on environmental
    variables defined by Bazel.

    As per docs, tests should not rely on any other environmental
    variables, so the framework will omit writing to file
    if necessary variables are undefined.
    See: https://docs.bazel.build/versions/master/test-encyclopedia.html#initial-conditions

    :returns: string representing path to the output directory
    :rtype: str
    :raises: RuntimeError if the environment variable is not set
    """
    output_dir_env_variable = "TEST_UNDECLARED_OUTPUTS_DIR"
    output_dir = os.environ.get(output_dir_env_variable)

    if not output_dir:
        output_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        if output_dir:
            output_dir = os.getcwd()
            logger.warning(f"Not a test runner. Test outputs will be saved to: {output_dir}")
        else:
            raise RuntimeError(
                f"Environment variable '{output_dir_env_variable}' used as the output directory is not set. "
                "Saving custom test results to a custom file will not be enabled."
            )

    return output_dir


def get_output_artifacts_dir():
    """
    Prepare the directory for the artifacts to be output.
    Will create the directory if it does not exist.

    :returns: string representing path to the artifacts directory
    :rtype: str
    :raises: RuntimeError if the path exists and is not a directory
    """
    output_artifacts_dir = os.path.join(get_output_dir(), "artifacts")

    if os.path.exists(output_artifacts_dir):
        if os.path.isdir(output_artifacts_dir):
            return output_artifacts_dir
        raise RuntimeError(f"Artifacts '{output_artifacts_dir}' directory path exists and is not a directory.")

    os.makedirs(output_artifacts_dir)
    return output_artifacts_dir


def get_repository_path():
    """
    Get the path to repository via bazel symlink.
    This only works under bazel test since it relies on the path provided by EnvVar TEST_UNDECLARED_OUTPUTS_DIR.
    Instead, under bazel run, such path is given by EnvVar BUILD_WORKSPACE_DIRECTORY.

    :returns: string representing path to repository
    :rtype: str
    :raises: CalledProcessError if the process exits with a non-zero exit code
    """
    bazel_link = f"{get_output_dir().split('bazel-out')[0]}/bazel"
    return (
        subprocess.run(["readlink", "-f", bazel_link], check=True, stdout=subprocess.PIPE)
        .stdout.decode("utf-8")
        .rpartition("bazel")[0]
    )
