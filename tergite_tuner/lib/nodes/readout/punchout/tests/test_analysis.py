# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import pytest
from matplotlib import pyplot as plt

from tergite_tuner.lib.nodes.readout.punchout.analysis import (
    analyse_punchout,
    plot_punchout,
    save_punchout_spectroscopies,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy import (
    analysis as resonator_analysis,
)
from tergite_tuner.tests.utils.datasets import get_s21


def _get_s21(node_data_dir, qubit: str = "q06"):
    return get_s21(node_data_dir / "dataset_punchout_0.hdf5", qubit)


@pytest.mark.parametrize(
    "qubit, amplitude",
    [("q06", 0.016), ("q07", 0.016), ("q10", 0.045), ("q12", 0.030), ("q15", 0.06)],
)
def test_amplitude_is_the_last_before_the_resonator_shifts(
    node_data_dir, qubit, amplitude
):
    fits = analyse_punchout(_get_s21(node_data_dir, qubit), None)

    assert fits["amplitude"].value == pytest.approx(amplitude, abs=0.001)


def test_punchout_fails_when_no_resonator_fit_succeeds(node_data_dir, monkeypatch):
    def _raise(*_args, **_kwargs):
        raise ValueError("fit diverged")

    monkeypatch.setattr(resonator_analysis.model, "fit", _raise)

    assert analyse_punchout(_get_s21(node_data_dir), None) is None


@pytest.mark.parametrize("is_fit", [True, False])
def test_punchout_plots_resonator_frequencies_against_amplitude(node_data_dir, is_fit):
    s21 = _get_s21(node_data_dir)
    fits = analyse_punchout(s21, None) if is_fit else {}
    figure, axis = plt.subplots()

    plot_punchout(axis, s21, fits, None)

    assert axis.get_xlabel() == "Readout pulse amplitude [V?]"
    if is_fit:
        fitted_points = axis.collections[1].get_offsets()
        amplitudes = s21.coords["ro_amplitudesq06"].values
        assert list(fitted_points[:, 0]) == pytest.approx(list(amplitudes))
    plt.close(figure)


def test_punchout_saves_each_amplitudes_spectroscopy(node_data_dir, tmp_path):
    s21 = _get_s21(node_data_dir)

    save_punchout_spectroscopies(s21, analyse_punchout(s21, None), tmp_path, None)

    assert (tmp_path / "punchout_q06_spectroscopies.png").exists()
