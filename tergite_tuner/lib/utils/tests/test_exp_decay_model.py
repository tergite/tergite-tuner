# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
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

from tergite_tuner.lib.utils.analysis_models import ExpDecayModel


def test_exponential_decay_model_initialization():
    model = ExpDecayModel()
    # Ensure the model has parameter hints for 'A', 'B', and 'p'
    assert "A" in model.param_hints
    assert "B" in model.param_hints
    assert "p" in model.param_hints
    # Verify that 'B' and 'p' have a minimum value of 0
    assert model.param_hints["B"]["min"] == 0
    assert model.param_hints["p"]["min"] == 0


def test_guess_defaults_to_half_and_the_last_point():
    data = np.array([1.0, 0.8, 0.6, 0.4, 0.2])

    params = ExpDecayModel().guess(data, m=np.arange(5))

    assert params["A"].value == pytest.approx(0.5)
    assert params["B"].value == pytest.approx(0.2)
    assert params["p"].value == pytest.approx(0.95)


def test_guess_takes_the_amplitude_and_offset_given():
    data = np.array([1.0, 0.8, 0.6, 0.4, 0.2])

    params = ExpDecayModel().guess(data, m=np.arange(5), amplitude=1.0, offset=0.8)

    assert params["A"].value == pytest.approx(1.0)
    assert params["B"].value == pytest.approx(0.8)
