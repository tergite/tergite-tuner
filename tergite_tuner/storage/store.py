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

import abc
from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, TypedDict

Value = str | float | int | bool | list | dict | None
Collection = Literal["transmons", "couplers", "cs"]
# each collection's records by element, each a flat mapping of colon-separated field paths
Records = Mapping[Collection, Mapping[str, Mapping[str, Value]]]


class QueryOptions(TypedDict, total=False):
    collection: Collection
    pk: str
    field: str
    value: Value


class QueryFunc(Protocol):
    """Whether a field belongs in a query's result."""

    def __call__(self, opts: QueryOptions) -> bool: ...


class Store(abc.ABC):
    """Each element's parameters, in ``transmons`` and ``couplers``, and its calibration statuses, in ``cs``.

    A record is an element's fields, keyed by its name (``q00``, ``q00_q01``); a value
    reads back with the type it was saved with.
    """

    @abc.abstractmethod
    def read_field(self, collection: Collection, pk: str, field_path: str) -> Value:
        """The field's value, or ``None`` if the record or the field is missing."""

    @abc.abstractmethod
    def save_many(self, records: Records, should_reset: bool = False) -> None:
        """Merges each record's fields into the stored one, or replaces it if ``should_reset``."""

    @abc.abstractmethod
    def find_many(
        self,
        collection: Collection | None = None,
        pks: Sequence[str] | None = None,
        query: QueryFunc | None = None,
    ) -> Records:
        """The records of ``collection``, or of all, for ``pks``, or for all, with the fields ``query`` matches."""

    @abc.abstractmethod
    def find_one(self, collection: Collection, pk: str) -> Mapping[str, Value]:
        """The record of ``pk``.

        Raises:
            KeyError: if the collection has no record of ``pk``.
        """
