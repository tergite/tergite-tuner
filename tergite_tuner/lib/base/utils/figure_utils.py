# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


import matplotlib.pyplot as plt
import numpy as np
from matplotlib import gridspec
from matplotlib.figure import Figure

SUBPLOT_SIZE = 5
# wider subplots for few columns, so the band's text fits
SUBPLOT_SIZES = {1: 16, 2: 8, 3: 5.5}
LOGO_SIZE = 0.8
BAND_HEIGHT = 0.8


def create_figure_with_top_band(nrows: int, ncols: int) -> tuple[Figure, np.ndarray]:
    """A figure with a blank band on top for metadata, over an ``nrows`` by ``ncols`` grid of axes."""
    subplot_size = SUBPLOT_SIZES.get(ncols, SUBPLOT_SIZE)
    width = ncols * subplot_size
    plots_height = nrows * subplot_size
    figure = plt.figure(figsize=(width, BAND_HEIGHT + plots_height))
    outer = gridspec.GridSpec(
        2, 1, height_ratios=[BAND_HEIGHT, plots_height], figure=figure
    )
    plot_grid = gridspec.GridSpecFromSubplotSpec(
        nrows, ncols, subplot_spec=outer[1], hspace=0.3, wspace=0.35
    )
    axes = np.array(
        [
            [figure.add_subplot(plot_grid[row, column]) for column in range(ncols)]
            for row in range(nrows)
        ]
    )
    _add_band(figure, outer[0], width)
    return figure, axes


def _add_band(figure: Figure, spec: gridspec.SubplotSpec, width: float) -> None:
    """Three blank axes across ``spec``: a logo's width at each end and the rest between."""
    band = gridspec.GridSpecFromSubplotSpec(
        1,
        3,
        subplot_spec=spec,
        wspace=0,
        width_ratios=[
            LOGO_SIZE / width,
            (width - 2 * LOGO_SIZE) / width,
            LOGO_SIZE / width,
        ],
    )
    for index in range(3):
        axis = figure.add_subplot(band[index])
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)
