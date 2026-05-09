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

from tergite_tuner.lib.nodes.characterization.purity_benchmarking.analysis import (
    ExpDecayModel,
)


def test_exponential_decay_model_initialization():
    model = ExpDecayModel()
    # Ensure the model has parameter hints for 'A', 'B', and 'p'
    assert "A" in model.param_hints
    assert "B" in model.param_hints
    assert "p" in model.param_hints
    # Verify that 'B' and 'p' have a minimum value of 0
    assert model.param_hints["B"]["min"] == 0
    assert model.param_hints["p"]["min"] == 0


def test_guess_parameters():
    model = ExpDecayModel()
    data = np.array([1.0, 0.8, 0.6, 0.4, 0.2])  # Example data
    m = np.array([0, 1, 2, 3, 4])  # Example m values
    params = model.guess(data, m=m)
    # Verify that the guessed parameters are close to expected values
    assert params["A"].value, pytest.approx(1.0)
    assert params["B"].value, pytest.approx(0.8)
    assert params["B"].value, pytest.approx(0.95)
