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

import os.path
from pathlib import Path

import pandas
import xarray as xr

import tergite_tuner.utils.reanalysis as ra_utils
from tergite_tuner.lib.nodes.coupler.cz_calibration.node import CZCalibrationNode
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    ResonatorSpectroscopyNode,
)
from tergite_tuner.storage.fs.dataset import save_dataset, scrape_and_copy_hdf5_files
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
    get_fixture_path,
)
from tergite_tuner.tests.utils.redis import loaded_redis
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon

_REDIS_FILE = get_fixture_path("redis/redis-2025-12-25-12-40-59.json")


def test_scrape_and_copy_hdf5_files(tmp_path):
    """
    Base case, copies all measurement files and counts whether they are in the target directory
    """
    scrape_directory = get_fixture_path(
        "data",
        "16-51-33_standard_run_ro_amplitude_three_state_optimization-SUCCESS",
    )
    target_directory = os.path.join(
        tmp_path,
        "16-51-33_standard_run_ro_amplitude_three_state_optimization-SUCCESS",
    )

    scrape_and_copy_hdf5_files(scrape_directory, target_directory)
    assert os.path.exists(target_directory)

    n_copied_files = os.listdir(target_directory)
    assert len(n_copied_files) == 4


def test_is_run_folder():
    """Check that the standard run test fixture is a run folder"""
    run_dir = get_fixture_path(
        "data",
        "16-51-33_standard_run_ro_amplitude_three_state_optimization-SUCCESS",
    )
    assert ra_utils.is_run_folder(run_dir)


def test_is_measurement_folder():
    """Check that the standard run test fixture contains the correct measurement folders"""
    run_dir = Path(
        get_fixture_path(
            "data",
            "16-51-33_standard_run_ro_amplitude_three_state_optimization-SUCCESS",
        )
    )
    measurement_folders = set(
        filter(lambda m: ra_utils.is_measurement_folder(m), run_dir.iterdir())
    )
    assert len(measurement_folders) == 4
    measurement_folders = set(map(lambda m: m.name, measurement_folders))

    assert measurement_folders == {
        "20250728-165136-525-9c2f16-resonator_spectroscopy",
        "20250728-165142-378-6c2eaa-qubit_01_spectroscopy",
        "20250728-165219-145-8960cd-rabi_oscillations",
        "20250728-165237-029-8e7bcc-ramsey_correction",
    }


def test_save_dataset(tmp_path, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node = ResonatorSpectroscopyNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_raw_dataset = node.generate_dummy_dataset()
    result_dataset = node.configure_dataset(dummy_raw_dataset)
    name = "resonator_spectroscopy"
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
    with loaded_redis(redis_connection, _REDIS_FILE) as conn:
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
