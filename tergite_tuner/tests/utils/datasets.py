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
"""Recorded datasets as the node analyses take them."""

from pathlib import Path

import xarray as xr


def get_s21(file_path: Path, qubit: str) -> xr.DataArray:
    """``qubit``'s complex S21 from a saved dataset, which splits it into real and imaginary parts."""
    with xr.open_dataset(file_path) as dataset:
        data = dataset[f"y{qubit}"].load()
    s21 = data.isel(ReIm=0) + 1j * data.isel(ReIm=1)
    s21.attrs = {**data.attrs, "qubit": qubit}
    return s21


def get_coupler_dataset(dataset: xr.Dataset, coupler: str, name: str) -> xr.Dataset:
    """``dataset``'s variables for ``coupler``, as a coupler node's analysis takes them."""
    variables = [
        var
        for var in dataset.data_vars.values()
        if var.attrs.get("element", coupler) == coupler
    ]
    return xr.merge(variables).load().assign_attrs(coupler=coupler, node=name)
