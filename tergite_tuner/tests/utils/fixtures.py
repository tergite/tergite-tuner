# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import json
from os import path
from typing import Any, Dict, List, Union

import yaml

_TESTS_FOLDER = path.dirname(path.dirname(path.abspath(__file__)))
_FIXTURES_PATH = path.join(_TESTS_FOLDER, "fixtures")

# Mirrors ``tests/fixtures/templates/default_device_under_test/configs/
# run_config.toml``. Tests previously read these values via
# ``CONFIG.run.qubits``/``CONFIG.run.couplers`` etc.; with the new pydantic
# config the run configuration is no longer carried on ``CONFIG`` and
# instead lives on a per-run :class:`SessionContext`. Tests that just need
# a stable default qubit/coupler set can use these constants directly.
DEFAULT_TEST_QUBITS: List[str] = ["q00", "q01"]
DEFAULT_TEST_COUPLERS: List[str] = ["q00_q01"]
DEFAULT_TEST_RUN_NAME: str = "no_name_for_this_run_set"
DEFAULT_TEST_TARGET_NODE: str = "ro_amplitude_two_state_optimization"


def load_fixture(
    file_name: str, fmt: str = "json"
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Loads the given fixture from the fixtures directory

    Args:
        file_name: the name of the file that contains the fixture
        fmt: file format e.g. json or yaml, default: json

    Returns:
        the list of dicts or the dict got from the json fixture file
    """
    fixture_path = get_fixture_path(file_name)
    with open(fixture_path, "rb") as file:
        if fmt == "json":
            return json.load(file)
        elif fmt == "yaml":
            return yaml.load(file, Loader=yaml.FullLoader)
        else:
            raise NotImplementedError(f"Cannot load fixture of format:{fmt}")


def get_fixture_path(*paths: str) -> str:
    """Gets the path to the fixture

    Args:
        paths: sections of paths to the given fixture e.g. fixtures/api/rest/rng_list.json
            would be "api", "rest", "rng_list.json"

    Returns:
        the path to the given fixture
    """
    return path.join(_FIXTURES_PATH, *paths)
