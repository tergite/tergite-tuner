# This code is part of Tergite
#
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

from tergite_tuner.lib.base.utils.figure_utils import create_figure_with_top_band


@pytest.mark.parametrize(
    "nrows, ncols, size", [(1, 1, (16, 16.8)), (2, 3, (16.5, 11.8)), (1, 5, (25, 5.8))]
)
def test_figure_sizes_its_subplots_by_columns_under_a_band(nrows, ncols, size):
    figure, axes = create_figure_with_top_band(nrows, ncols)
    try:
        assert axes.shape == (nrows, ncols)
        assert tuple(figure.get_size_inches()) == pytest.approx(size)
        assert len(figure.axes) == nrows * ncols + 3
    finally:
        plt.close(figure)
