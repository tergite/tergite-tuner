# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


import pandas
import xarray as xr

from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.lib.nodes.coupler.cz_calibration.node import CZCalibrationNode
from tergite_tuner.storage.fs.dataset import save_dataset
from tergite_tuner.tests.utils.fixtures import (
    get_fixture_path,
)
from tergite_tuner.tests.utils.goldens import get_dataset_builder
from tergite_tuner.tests.utils.redis import loaded_redis

_REDIS_FILE = get_fixture_path("redis/redis-2025-12-25-12-40-59.json")


def test_save_dataset(tmp_path, session_context):
    name = "resonator_spectroscopy"
    result_dataset = get_dataset_builder(name, session_context)()
    results_file = tmp_path / f"dataset_{name}.hdf5"

    try:
        save_dataset(result_dataset, name, tmp_path)
        assert results_file.exists()
    finally:
        results_file.unlink(missing_ok=True)


def test_save_dataset_with_working_points(tmp_path, redis_connection, session_context):
    """
    for nodes like cz calibration where two coords are packed into a Multindex object
    """
    with loaded_redis(redis_connection, _REDIS_FILE):
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        coupler = "q13_q14"
        couplers = [coupler]
        node = CZCalibrationNode(
            session=session_context, all_qubits=["q13", "q14"], couplers=couplers
        )

        dummy_raw_dataset_1 = node.generate_dummy_dataset()
        result_dataset_1 = node.configure_dataset(dummy_raw_dataset_1)
        multi_index = pandas.MultiIndex.from_tuples([(7e8, 200e-9)], names=["l1", "l2"])
        result_dataset_1 = result_dataset_1.expand_dims({"working_points": multi_index})
        result_dataset_1 = result_dataset_1.assign_coords(
            {"working_points": ("working_points", multi_index)}
        )

        dummy_raw_dataset_2 = node.generate_dummy_dataset()
        result_dataset_2 = node.configure_dataset(dummy_raw_dataset_2)
        multi_index = pandas.MultiIndex.from_tuples([(8e8, 250e-9)], names=["l1", "l2"])
        result_dataset_2 = result_dataset_2.expand_dims({"working_points": multi_index})
        result_dataset_2 = result_dataset_2.assign_coords(
            {"working_points": ("working_points", multi_index)}
        )

        result_dataset = xr.merge(
            [result_dataset_1, result_dataset_2], join="outer", compat="no_conflicts"
        )

        name = "cz_calibration"
        save_path = tmp_path / f"dataset_{name}.hdf5"
        loaded_dataset = None

        try:
            save_dataset(result_dataset, name, tmp_path)
            assert save_path.exists()

            loaded_dataset = xr.open_dataset(save_path)
            loaded_dataset.close()
            assert "working_points" in loaded_dataset
            assert "l1" in loaded_dataset
            assert "l2" in loaded_dataset
        finally:
            save_path.unlink(missing_ok=True)
            if loaded_dataset:
                loaded_dataset.close()
