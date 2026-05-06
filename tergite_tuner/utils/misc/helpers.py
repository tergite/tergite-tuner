# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import Any, Dict, Iterator, List
from typing import Mapping
from typing import Mapping as MappingABC
from typing import Tuple


def generate_n_qubit_list(n_qubits: int, starting_from: int = 1) -> List[str]:
    """
    This generates a list of qubits.

    Args:
        n_qubits: The number of qubits.
        starting_from: Start counting from when numbering the qubits (default: 1).

    Returns:
        List of qubits ["qXX", ...] starting with "q01" (default, regulated by starting_from parameter).
    """
    return [f"q{i:02}" for i in range(starting_from, starting_from + n_qubits)]


def update_nested(target: Dict, updates: Dict) -> None:
    """
    Update a nested data structure (usually a dict).

    Args:
        target: The original data structure
        updates: The updates that are going to be merged into the data structure

    Returns:
        None: Does not return anything, but works on the given objects

    """
    for key, value in updates.items():
        if key in target:
            # If the key exists in target, check if both values are dicts
            if isinstance(value, dict) and isinstance(target[key], dict):
                # Recursively update nested dictionaries without overwriting
                update_nested(target[key], value)
            else:
                # Skip if the key exists and is not a dictionary
                continue
        else:
            # If the key does not exist in target, add it
            target[key] = value


def insert_nested_key(data: Dict[str, Any], path: Tuple[str, ...], value: Any):
    """Inserts inplace a given value at the given nested path in the data object

    Args:
        data: the dictionary to insert into
        path: the path to the field, as a tuple of path segments.
        value: the value to be inserted.
    """
    inner_record = data
    for segment in path[:-1]:
        inner_record = inner_record.setdefault(segment, {})

    inner_record[path[-1]] = value


def to_flat_map(
    value: Mapping[str, Any], sep: str = ":", key_prefix: str = ""
) -> Iterator[Tuple[str, Any]]:
    """Flatten a nested map into a flat iterator of tuple of ``sep``-separated key and value
    Args:
        value: The map to flatten.
        sep: the separator between keys
        key_prefix: the prefix to insert before the keys

    Returns:
        The iterator.
    """
    for k, v in value.items():
        key = f"{key_prefix}{k}"
        if isinstance(v, MappingABC):
            yield from to_flat_map(v, sep=sep, key_prefix=f"{key}{sep}")
        else:
            yield key, v


def to_nested_dict(value: Mapping[str, Any], sep: str = ":") -> Dict[str, Any]:
    """Makes a map nested by splitting the keys on ``sep``
    Args:
        value: The map to flatten.
        sep: the separator between keys

    Returns:
        The nested dict.
    """
    result = {}
    for k, v in value.items():
        path = tuple(k.split(sep))
        insert_nested_key(result, path=path, value=v)

    return result
