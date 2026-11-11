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
"""Pins the figures each node saves for a recorded dataset to what they drew when this test was added.

The figures are caught as the node saves them, so the golden holds whichever code draws
them. A change that alters a figure on purpose rewrites its golden with
``UPDATE_GOLDENS=1 pytest tergite_tuner/tests/test_figure_goldens.py``, and the commit
says why. ``SAVE_FIGURES=<folder>`` also saves each figure there, to look at.
"""

import json
import os
from pathlib import Path

import pytest
from matplotlib.figure import Figure

from tergite_tuner.tests.utils.figures import (
    RELATIVE_TOLERANCE,
    get_figure_snapshot,
    get_mismatches,
)
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import (
    RECORDED_DATASETS,
    get_analyser,
    get_state_file,
)
from tergite_tuner.tests.utils.state import loaded_state

GOLDENS_DIR = Path(get_fixture_path("goldens", "figures"))
# the resonator fits these figures draw differ between macOS's Accelerate and Linux's
# OpenBLAS: their frequencies by ~1e-6, their curves by up to 1.4% and the spread of
# their frequencies over the currents by up to 0.7%; the artists and labels stay exact
LOOSE_TOLERANCES = {
    "standard_run_resonator_spectroscopy": 1e-3,
    "punchout": 2e-2,
    "resonator_spectroscopy_vs_current": 2e-2,
}
# platforms fit q08's punchout either side of a threshold, as the reanalysis goldens allow
UNSTABLE_ELEMENTS = {"punchout": "q08"}


@pytest.mark.parametrize("case", RECORDED_DATASETS)
def test_reanalysis_saves_the_golden_figures(
    case, session_context, tmp_path, monkeypatch
):
    golden_case = RECORDED_DATASETS[case]
    snapshots = {}
    save = Figure.savefig
    figures_dir = os.environ.get("SAVE_FIGURES")

    def record(figure, path, *_args, **_kwargs):
        name = Path(path).stem.removesuffix("_preview")
        if name in snapshots:
            return
        snapshots[name] = get_figure_snapshot(figure)
        if figures_dir:
            Path(figures_dir, case).mkdir(parents=True, exist_ok=True)
            save(figure, Path(figures_dir, case, f"{name}.png"), bbox_inches="tight")

    monkeypatch.setattr(Figure, "savefig", record)
    analyse = get_analyser(
        golden_case, tmp_path, session_context, should_save_plot=True
    )
    with loaded_state(session_context, get_state_file(golden_case)):
        analyse()

    golden_path = GOLDENS_DIR / f"{case}.json"
    if os.environ.get("UPDATE_GOLDENS"):
        GOLDENS_DIR.mkdir(exist_ok=True)
        golden_path.write_text(json.dumps(snapshots, indent=1, sort_keys=True) + "\n")
    golden = json.loads(golden_path.read_text())
    tolerance = LOOSE_TOLERANCES.get(case, RELATIVE_TOLERANCE)
    if case in UNSTABLE_ELEMENTS:
        snapshots = _get_without_element(snapshots, UNSTABLE_ELEMENTS[case])
        golden = _get_without_element(golden, UNSTABLE_ELEMENTS[case])
    assert snapshots, "the node saved no figure"
    mismatches = get_mismatches(snapshots, golden, tolerance)
    assert not mismatches, "\n".join(mismatches)


def _get_without_element(snapshots: dict, element: str) -> dict:
    """The snapshots without the element's own figures, or its axes in the others."""
    return {
        name: {
            **snapshot,
            "axes": [
                axes
                for axes in snapshot["axes"]
                if axes["titles"].get("center", {}).get("text") != f"Qubit {element}"
            ],
        }
        for name, snapshot in snapshots.items()
        if f"_{element}_" not in name
    }
