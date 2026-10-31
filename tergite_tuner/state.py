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

import copy
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Literal

from tergite_tuner.utils.dicts import insert_nested_key

Collection = Literal["transmons", "couplers", "cs"]
# each collection's records by element; a record nests its fields by their colon-separated paths
Records = dict[Collection, dict[str, dict[str, Any]]]

COLLECTIONS: tuple[Collection, ...] = ("transmons", "couplers", "cs")


class DeviceState:
    """A run's device values, in ``transmons`` and ``couplers``, and calibration statuses, in ``cs``.

    ``load`` merges values a run starts from, ``write`` the values it calibrates, whose
    parameter paths ``written_paths`` keeps until cleared. A node's config overrides sit
    over the values while it runs.
    """

    def __init__(
        self, records: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None
    ):
        self._records: Records = {collection: {} for collection in COLLECTIONS}
        self._overrides: Records = {collection: {} for collection in COLLECTIONS}
        self.written_paths: set[str] = set()
        self.load(records or {})

    def read(self, collection: Collection, element: str, path: str) -> Any:
        """The value at the colon-separated ``path``, or ``None`` if it is missing.

        Args:
            collection: ``transmons``, ``couplers`` or ``cs``.
            element: the qubit or coupler.
            path: the field's path, such as ``rxy:amp180``.

        Returns:
            The value, with any override over it.
        """
        value: Any = self.get_record(collection, element)
        for segment in path.split(":"):
            if not isinstance(value, Mapping) or segment not in value:
                return None
            value = value[segment]
        return value

    def get_record(self, collection: Collection, element: str) -> dict[str, Any]:
        """A copy of the element's record, with the overrides over it.

        Args:
            collection: ``transmons``, ``couplers`` or ``cs``.
            element: the qubit or coupler.

        Returns:
            The record's fields, nested; empty if the element has none.
        """
        record = copy.deepcopy(self._records[collection].get(element, {}))
        _merge_record(record, self._overrides[collection].get(element, {}))
        return record

    def get_records(
        self,
        elements: Iterable[str] | None = None,
        should_keep_field: Callable[[str], bool] | None = None,
    ) -> Records:
        """A copy of the records of ``elements``, or of all, without the overrides.

        Args:
            elements: the qubits and couplers to copy; all if None.
            should_keep_field: picks a record's top-level fields; all if None.

        Returns:
            The records by collection and element; elements left with no field are
            dropped.
        """
        records: Records = {}
        for collection, collection_records in self._records.items():
            for element, record in collection_records.items():
                if elements is not None and element not in elements:
                    continue
                fields = {
                    field: copy.deepcopy(value)
                    for field, value in record.items()
                    if should_keep_field is None or should_keep_field(field)
                }
                if fields:
                    records.setdefault(collection, {})[element] = fields
        return records

    def load(self, records: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
        """Merges ``records``, whose fields may be nested or colon-separated paths.

        Args:
            records: by collection, then element, each element's fields.
        """
        _merge(self._records, records)

    def write(self, records: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
        """Merges ``records``, as ``load`` does, and keeps their parameter paths.

        Args:
            records: by collection, then element, each element's fields; paths in
                ``cs`` are not kept.
        """
        _merge(self._records, records)
        for collection, collection_records in records.items():
            if collection != "cs":
                for record in collection_records.values():
                    self.written_paths.update(record)

    def add_overrides(
        self, records: Mapping[str, Mapping[str, Mapping[str, Any]]]
    ) -> None:
        """Sets values over the records until ``clear_overrides``, as a node's config does.

        Args:
            records: by collection, then element, each element's fields.
        """
        _merge(self._overrides, records)

    def clear_overrides(self) -> None:
        """Drops every override, leaving the records as loaded and written."""
        self._overrides = {collection: {} for collection in COLLECTIONS}

    def __deepcopy__(self, memo: dict) -> "DeviceState":
        state = DeviceState(self._records)
        state._overrides = copy.deepcopy(self._overrides, memo)
        state.written_paths = set(self.written_paths)
        return state


def _merge(
    target: Records, records: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> None:
    for collection, collection_records in records.items():
        for element, record in collection_records.items():
            _merge_record(target[collection].setdefault(element, {}), record)


def _merge_record(target: dict[str, Any], record: Mapping[str, Any]) -> None:
    for field, value in record.items():
        if isinstance(value, Mapping):
            _merge_record(target.setdefault(field, {}), value)
        else:
            insert_nested_key(target, tuple(field.split(":")), copy.deepcopy(value))
