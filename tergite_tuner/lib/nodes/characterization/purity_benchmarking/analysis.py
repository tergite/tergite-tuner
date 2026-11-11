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

"""Purity benchmarking's analysis: the purity's decay per Clifford."""

from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits
from tergite_tuner.lib.utils.analysis_models import ExpDecayModel
from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

# the last points are the |0>, |1> and spare calibration points
CALIBRATION_POINTS = 3
CURVE_POINTS = 400


class PurityCurves(NamedTuple):
    """The purities and the fitted decay, to plot.

    Attributes:
        cliffords: the numbers of Cliffords measured.
        purities: each seed's purity per number of Cliffords.
        curve_cliffords: the numbers of Cliffords the fitted curve is evaluated at.
        curve: the fitted decay at ``curve_cliffords``.
        best_fit: the fitted decay at ``cliffords``.
    """

    cliffords: np.ndarray
    purities: list[list[float]]
    curve_cliffords: np.ndarray
    curve: np.ndarray
    best_fit: np.ndarray


def analyse_purity_benchmarking(s21: xr.DataArray, _session: "SessionContext") -> Fits:
    """Fits an exponential decay to the purity, averaged over the seeds, against the number of Cliffords.

    Each seed's shots are rotated and scaled by its |0> and |1> calibration points,
    and each Clifford sequence's X, Y and Z measurements give its purity.

    Args:
        s21: the qubit's S21, a point per measurement and seed.
        _session: unused; part of the ``analyse`` signature.

    Returns:
        ``purity_fidelity``, the purity's decay per Clifford, and, to plot, the
        ``curves``.
    """
    cliffords_coord = _find_coord(s21, "cliffords")
    seed_coord = _find_coord(s21, "seed")
    cliffords = np.unique(s21[cliffords_coord].values[:-CALIBRATION_POINTS])
    normalised = [
        _get_normalised(s21.isel({seed_coord: seed}).values.flatten())
        for seed in range(s21.sizes[seed_coord])
    ]
    purities = [_get_purities(values) for values in normalised]
    average_purity = np.sum(purities, axis=0) / len(purities)
    logger.info(np.sum(normalised, axis=0) / len(normalised))
    logger.info(average_purity)

    model = ExpDecayModel()
    guess = model.guess(
        data=average_purity,
        m=cliffords,
        amplitude=average_purity[0],
        offset=average_purity[-4],
    )
    result = model.fit(average_purity, params=guess, m=cliffords)
    curve_cliffords = np.linspace(cliffords[0], cliffords[-1], CURVE_POINTS)
    curves = PurityCurves(
        cliffords,
        purities,
        curve_cliffords,
        model.eval(result.params, m=curve_cliffords),
        result.best_fit,
    )
    return {
        "purity_fidelity": Fit(result.params["p"].value, np.nan),
        "curves": Fit(curves),
    }


def plot_purity_benchmarking(
    axis: Axes, _s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """Draws each seed's purity, numbered, and the fitted decay.

    Args:
        axis: the axis to draw on.
        _s21: unused; part of the ``plot`` signature.
        fits: the qubit's fits; nothing is drawn if empty.
        _session: unused; part of the ``plot`` signature.
    """
    if not fits:
        return
    curves = fits["curves"].value
    for seed, purities in enumerate(curves.purities):
        axis.plot(curves.cliffords, purities, alpha=0.2)
        axis.annotate(f"{seed}", (curves.cliffords[-1], purities[-1]))
    axis.plot(
        curves.curve_cliffords,
        curves.curve,
        "ro-",
        lw=2.5,
        label=f"p = {fits['purity_fidelity'].value:.3f}",
    )
    axis.plot(curves.cliffords, curves.best_fit, ls="dashed", color="black")
    axis.set_ylabel("Purity")
    axis.set_xlabel("Number of Cliffords")
    axis.grid()


def _find_coord(array: xr.DataArray, part: str) -> str:
    """The array's coordinate whose name holds ``part``; recorded datasets differ in the suffix."""
    return next(str(coord) for coord in array.coords if part in str(coord))


def _get_normalised(measurements: np.ndarray) -> np.ndarray:
    """A seed's measurements rotated and scaled so its |0> calibration is 0 and its |1> is 1."""
    data = measurements[:-CALIBRATION_POINTS]
    calibration_0, calibration_1 = measurements[-3], measurements[-2]
    rotation = np.exp(-1j * np.angle(calibration_1 - calibration_0))
    rotated = (data - calibration_0) * rotation
    scale = (calibration_1 * rotation - calibration_0 * rotation).real
    return rotated.real / scale


def _get_purities(normalised: np.ndarray) -> list[float]:
    """Each Clifford sequence's purity, from its normalised X, Y and Z measurements in turn."""
    purities = []
    for index in range(len(normalised) // 3):
        x, y, z = 2 * normalised[3 * index : 3 * (index + 1)] - 1
        purities.append(x**2 + y**2 + z**2)
    return purities
