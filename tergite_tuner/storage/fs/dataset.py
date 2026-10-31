# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Tong Liu 2024
# (C) Copyright Michele Faucci Giannelli 2024, 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cf_xarray as cf
import xarray

from tergite_tuner.utils.logging import logger


def to_real_dataset(iq_dataset: xarray.Dataset) -> xarray.Dataset:
    """The complex ``iq_dataset`` as real numbers, for a file format without complex ones.

    Args:
        iq_dataset: the dataset of complex S21.

    Returns:
        The dataset with a last ``ReIm`` dimension: the real part, then the imaginary.
    """
    ds = iq_dataset.expand_dims("ReIm", axis=-1)  # Add ReIm axis at the end
    ds = xarray.concat([ds.real, ds.imag], dim="ReIm")
    return ds


def get_unique_data_path(parent: Path, name: str) -> Path:
    """A new folder's path in ``parent``, named for the time, a random id and ``name``; not created.

    Args:
        parent: the folder to put it in.
        name: the end of its name, such as the node's.

    Returns:
        The folder's path.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:19]
    return Path(parent) / f"{timestamp}-{str(uuid4())[:6]}-{name}"


def load_dataset(node_name: str, data_path: Path) -> xarray.Dataset:
    """The dataset ``save_dataset`` saved for ``node_name`` in ``data_path``.

    Args:
        node_name: the node whose dataset to load.
        data_path: the node's data folder.

    Returns:
        The dataset, its ``working_points`` decoded if it has them.

    Raises:
        FileNotFoundError: if the folder has no dataset for the node.
    """
    dataset_path = Path(data_path) / f"dataset_{node_name}.hdf5"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    logger.info(f"Open dataset {dataset_path}")
    dataset = xarray.open_dataset(dataset_path)
    if "working_points" in dataset.coords:
        dataset = cf.decode_compress_to_multi_index(dataset, "working_points")
    return dataset


def save_dataset(
    result_dataset: xarray.Dataset, node_name: str, data_path: Path
) -> None:
    """
    Save the measurement dataset to a file.

    Args:
        result_dataset (xarray.Dataset): The dataset to save.
        node_name (str): Name of the node being measured.
        data_path (Path): Path where the dataset will be saved.
    """
    data_path.mkdir(parents=True, exist_ok=True)
    measurement_id = data_path.stem[0:19]

    result_dataset = result_dataset.assign_attrs(
        {"name": node_name, "tuid": measurement_id}
    )

    # to_netcdf doesn't like complex numbers, convert to real&imag to save:
    result_dataset_real = to_real_dataset(result_dataset)

    dataset_name = f"dataset_{node_name}.hdf5"
    if "working_points" in result_dataset_real.coords:
        result_dataset_real = cf.encode_multi_index_as_compress(
            result_dataset_real, "working_points"
        )
    result_dataset_real.to_netcdf(data_path / dataset_name)
