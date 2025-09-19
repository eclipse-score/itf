import os
import sys
import pytest
import itf.plugins.utils.bazel as bazel


if __name__ == "__main__":
    args = sys.argv[1:]
    args += [f"--junitxml={os.path.join(bazel.get_output_dir(), 'itf-results.xml')}"]
    sys.exit(pytest.main(args))
