# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for :mod:`tergite_tuner.utils.reanalysis_utils`.

Reanalysis traverses three nested levels of folders that the
calibration produces: ``out/<YYYY-MM-DD>/<HH-MM-SS>_<run_label>/<measurement_folder>``.
Each level is identified by a regex match plus an existence check.
The tests build a mini fixture tree under ``tmp_path`` and exercise
the matchers and the *get_*_infos* walkers end-to-end.
"""

import os
from datetime import date, time

import pytest

from tergite_tuner.utils.reanalysis_utils import (
    DayInfo,
    MeasurementInfo,
    RunInfo,
    get_day_infos,
    get_run_infos,
    is_day_folder,
    is_measurement_folder,
    is_run_folder,
    search_all_runs_for_measurement,
)


def _make_measurement_folder(parent, name, with_dataset=True):
    folder = parent / name
    folder.mkdir(parents=True)
    if with_dataset:
        (folder / "dataset.hdf5").write_bytes(b"")
    return folder


def _build_data_tree(root):
    """Build:
    out/
      2025-07-28/
        16-51-33_run-OK/
          20250728-165136-525-9c2f16-resonator_spectroscopy/
          20250728-165142-378-6c2eaa-qubit_01_spectroscopy/   (no .hdf5)
        17-00-00_run-AGAIN/
          20250728-170100-000-9c2f16-resonator_spectroscopy/
      2025-07-29/
        08-00-00_morning-OK/
          20250729-080100-000-9c2f16-resonator_spectroscopy/
    """
    day1 = root / "2025-07-28"
    run1 = day1 / "16-51-33_run-OK"
    _make_measurement_folder(run1, "20250728-165136-525-9c2f16-resonator_spectroscopy")
    _make_measurement_folder(
        run1,
        "20250728-165142-378-6c2eaa-qubit_01_spectroscopy",
        with_dataset=False,
    )

    run2 = day1 / "17-00-00_run-AGAIN"
    _make_measurement_folder(run2, "20250728-170100-000-9c2f16-resonator_spectroscopy")

    day2 = root / "2025-07-29"
    run3 = day2 / "08-00-00_morning-OK"
    _make_measurement_folder(run3, "20250729-080100-000-9c2f16-resonator_spectroscopy")
    return day1, day2, run1, run2, run3


@pytest.fixture
def data_tree(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    return out, *_build_data_tree(out)


def test_is_day_folder(data_tree):
    """``YYYY-MM-DD`` directory matches and is reported."""
    out, day1, day2, *_ = data_tree
    assert is_day_folder(day1)
    assert is_day_folder(day2)
    assert not is_day_folder(out)


def test_is_run_folder(data_tree):
    """``HH-MM-SS_<label>-<status>`` directory matches."""
    _out, _day1, _day2, run1, run2, run3 = data_tree
    assert is_run_folder(run1)
    assert is_run_folder(run2)
    assert is_run_folder(run3)


def test_is_measurement_folder(data_tree):
    """A measurement folder matches; a run folder doesn't."""
    _out, _day1, _day2, run1, *_ = data_tree
    msmts = list(run1.iterdir())
    assert all(is_measurement_folder(m) for m in msmts)
    assert not is_measurement_folder(run1)


def test_matchers_reject_files(tmp_path):
    """Files (vs. directories) are never considered folders."""
    f = tmp_path / "2025-07-28"
    f.write_text("not a directory")
    assert not is_day_folder(f)
    assert not is_run_folder(f)
    assert not is_measurement_folder(f)


def test_matchers_reject_unmatched_names(tmp_path):
    """Directories whose names don't fit the regex are rejected even if they exist."""
    bad = tmp_path / "not-a-day-folder"
    bad.mkdir()
    assert not is_day_folder(bad)
    assert not is_run_folder(bad)
    assert not is_measurement_folder(bad)


def test_get_run_infos_returns_one_per_run_folder(data_tree):
    """``get_run_infos`` enumerates all run folders, indexed from 1."""
    _out, day1, _day2, _run1, _run2, _run3 = data_tree
    runs = get_run_infos(day1)

    assert len(runs) == 2
    assert all(isinstance(r, RunInfo) for r in runs)
    assert {r.timestamp for r in runs} == {time(16, 51, 33), time(17, 0, 0)}
    # run_idx is assigned in folder-name order
    sorted_by_idx = sorted(runs, key=lambda r: r.run_idx)
    assert [r.run_idx for r in sorted_by_idx] == [1, 2]


def test_get_run_infos_filters_to_measurements_with_hdf5(data_tree):
    """Measurements without an .hdf5 file are excluded from the returned info."""
    _out, day1, *_ = data_tree
    runs = get_run_infos(day1)
    first_run = next(r for r in runs if r.timestamp == time(16, 51, 33))
    msmt_names = {m.measurement_folder_path.name for m in first_run.measurements}
    # only the resonator_spectroscopy folder has an .hdf5; the qubit_01_spectroscopy one doesn't
    assert msmt_names == {
        "20250728-165136-525-9c2f16-resonator_spectroscopy",
    }


def test_get_run_infos_raises_for_non_day_folder(tmp_path):
    """A path that isn't a day folder raises ``FileNotFoundError``."""
    not_a_day = tmp_path / "nope"
    not_a_day.mkdir()
    with pytest.raises(FileNotFoundError):
        get_run_infos(not_a_day)


def test_get_day_infos_returns_sorted_days(data_tree):
    """All matching ``YYYY-MM-DD`` folders are returned sorted by date."""
    out, *_ = data_tree
    days = get_day_infos(out)
    assert len(days) == 2
    assert all(isinstance(d, DayInfo) for d in days)
    assert [d.timestamp for d in days] == [date(2025, 7, 28), date(2025, 7, 29)]


def test_get_day_infos_raises_when_out_missing(tmp_path):
    """A missing ``out`` folder raises ``FileNotFoundError``."""
    missing = tmp_path / "out"
    with pytest.raises(FileNotFoundError):
        get_day_infos(missing)


def test_search_all_runs_for_measurement_finds_by_name(data_tree):
    """A measurement is locatable by its folder name alone."""
    out, *_ = data_tree
    info = search_all_runs_for_measurement(
        out,
        "20250728-170100-000-9c2f16-resonator_spectroscopy",
    )
    assert isinstance(info, MeasurementInfo)
    assert info.node_name == "resonator_spectroscopy"


def test_search_all_runs_for_measurement_returns_none_when_missing(data_tree):
    """Unknown identifiers yield ``None``."""
    out, *_ = data_tree
    assert search_all_runs_for_measurement(out, "does-not-exist") is None
