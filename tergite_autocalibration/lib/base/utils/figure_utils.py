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

import os.path
from datetime import datetime
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import gridspec
from matplotlib.lines import Line2D

from tergite_autocalibration.utils.logging import logger


def _infer_date_from_path(path: str) -> str:
    try:
        path = Path(path)
        # Try multiple formats in case of different naming conventions
        for part in path.parts:
            try:
                return datetime.strptime(part, "%Y-%m-%d").strftime("%d-%m-%Y")
            except ValueError:
                pass

            # If no format matches, return folder creation time as fallback
        return datetime.fromtimestamp(path.stat().st_ctime).strftime("%d-%m-%Y")
    except Exception:
        return "Unknown"


def create_figure_with_top_band(nrows, ncols) -> tuple:
    """
    Create a figure with a top band for metadata and a grid of subplots.
    Args:
        nrows (int): Number of rows in the subplot grid.
        ncols (int): Number of columns in the subplot grid.
    Returns:
        fig (matplotlib.figure.Figure): The created figure.
        axs (numpy.ndarray): 2D array of Axes objects for the subplots.
    """
    # These values are fixed to ensure uniformity in the plots across the application.
    subplot_size = 5
    logo_size = 0.8
    band_height_inch = 0.8
    # This will fine tune the figure size based on the number of columns so that the writing no top fits
    if ncols == 1:
        subplot_size = 16
    elif ncols == 2:
        subplot_size = 8
    elif ncols == 3:
        subplot_size = 5.5

    fig_width = ncols * subplot_size
    subplot_area_height = nrows * subplot_size
    fig_height = band_height_inch + subplot_area_height

    fig = plt.figure(figsize=(fig_width, fig_height))

    # Outer GridSpec: 1 row for top band + 1 row for the subplot area
    outer = gridspec.GridSpec(
        2, 1, height_ratios=[band_height_inch, subplot_area_height], figure=fig
    )

    # Subplots (nrows x ncols) — this is the only one with spacing!
    plot_gs = gridspec.GridSpecFromSubplotSpec(
        nrows, ncols, subplot_spec=outer[1], hspace=0.3, wspace=0.35
    )

    axs = np.array(
        [[fig.add_subplot(plot_gs[i, j]) for j in range(ncols)] for i in range(nrows)]
    )

    center_width_inch = fig_width - 2 * logo_size
    left_frac = logo_size / fig_width
    center_frac = center_width_inch / fig_width
    right_frac = logo_size / fig_width

    band_gs = gridspec.GridSpecFromSubplotSpec(
        1,
        3,
        subplot_spec=outer[0],
        wspace=0,
        width_ratios=[left_frac, center_frac, right_frac],
    )
    ax_left = fig.add_subplot(band_gs[0])
    ax_center = fig.add_subplot(band_gs[1])
    ax_right = fig.add_subplot(band_gs[2])

    for ax in (ax_left, ax_center, ax_right):
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    return fig, axs
