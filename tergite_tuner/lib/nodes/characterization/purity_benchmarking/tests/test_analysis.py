# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
# (C) Copyright Michele Faucci Giannelli 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


import numpy as np
import pytest
from matplotlib.figure import Figure

from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.nodes.characterization.purity_benchmarking.analysis import (
    analyse_purity_benchmarking,
    plot_purity_benchmarking,
)
from tergite_tuner.tests.utils.datasets import get_s21

_HDF_FILENAME = "dataset_purity_benchmarking_0.hdf5"


@pytest.fixture
def fits(node_data_dir):
    return analyse_purity_benchmarking(
        get_s21(node_data_dir / _HDF_FILENAME, "q06"), SessionContext()
    )


def test_purity_decays_by_its_fitted_fidelity_per_clifford(fits):
    assert fits["purity_fidelity"].value == pytest.approx(0.9971567106)


def test_purity_is_averaged_from_each_seed(fits):
    purities = fits["curves"].value.purities

    assert len(purities) == 1
    assert 0.7 < np.average(purities) < 0.8


def test_plot_draws_the_seeds_and_the_fitted_decay(fits):
    axis = Figure().subplots()

    plot_purity_benchmarking(axis, None, fits, None)

    # the seed's purities, the fitted curve and the fit at the measured points
    assert len(axis.lines) == 3
    assert axis.lines[1].get_label() == "p = 0.997"
