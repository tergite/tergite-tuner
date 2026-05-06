# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Chalmers Next Labs AB 2024
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import ast
import json
from collections.abc import Mapping as MappingABC
from contextlib import suppress
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    TypedDict,
    Union,
)

import numpy as np
from redis import Redis

from tergite_tuner.utils.dto.qoi import QOI
from tergite_tuner.utils.misc.helpers import insert_nested_key

np.set_printoptions(legacy="1.25")


_Value = Union[str, float, int, bool, list, dict, None]
_Collection = Literal["transmons", "couplers", "cs"]
_RedisStoreObject = Mapping[_Collection, Mapping[str, Mapping[str, _Value]]]

# The prefix for the hashes that keep types data
_TYPES_COLLECTION = "__types__"

# Stable labels persisted for python types. ``bool`` precedes ``int`` because
# ``isinstance(True, int)`` is also true.
_TYPE_LABELS: Dict[type, str] = {
    bool: "bool",
    int: "int",
    float: "float",
    str: "str",
    list: "list",
    tuple: "list",
    dict: "dict",
    type(None): "none",
}

_SAVE_FIELD_LUA = f"""
-- v0.0.1
-- Atomically write a field's value and its type label so the canonical
-- hash and its sidecar can never get out of sync.
-- The types are stored in the {_TYPES_COLLECTION} collection under 
-- the same key but prepended with "{_TYPES_COLLECTION}:"
--
-- KEYS[1] = hash_key
-- ARGV[1] = field
-- ARGV[2] = value
-- ARGV[3] = type

local redis_call = redis.call

local hash_key = KEYS[1]
local type_key = "{_TYPES_COLLECTION}:" .. hash_key

redis_call('HSET', hash_key, ARGV[1], ARGV[2])
redis_call('HSET', type_key, ARGV[1], ARGV[3])
return 1
"""

_READ_FIELD_LUA = f"""
-- v0.0.1
-- Atomically read a field's value and its type label.
-- The types are stored in the {_TYPES_COLLECTION} collection under 
-- the same key but prepended with "{_TYPES_COLLECTION}:"
--
-- KEYS[1] = hash_key
-- ARGV[1] = field

local redis_call = redis.call

local hash_key = KEYS[1]
local type_key = "{_TYPES_COLLECTION}:" .. hash_key

local value = redis_call('HGET', hash_key, ARGV[1])
local label = redis_call('HGET', type_key, ARGV[1])
return {{value, label}}
"""

_SAVE_HASH_LUA = f"""
-- v0.0.1
-- Bulk-write every field of a single primary key. 
-- ARGV layout:
-- [reset_flag, field_count, field_1, value_1, type_1, ...]
--
-- When ``reset`` is 1 the canonical hash and its sidecar are deleted
-- before the new fields are written, yielding a fresh record. 
-- When ``reset`` is 0 the writes are merged on top of any pre-existing
-- record: fields that share a name are overwritten, the rest are left
-- untouched.
--
-- The types are stored in the {_TYPES_COLLECTION} collection under 
-- the same key but prepended with "{_TYPES_COLLECTION}:"
--

local redis_call = redis.call
local to_num = tonumber
local insert = table.insert
local unpack = unpack or table.unpack -- Compatibility check

local hash_key = KEYS[1]
local type_key = "{_TYPES_COLLECTION}:" .. hash_key

local reset_flag = to_num(ARGV[1])
if reset_flag == 1 then
    redis_call('DEL', hash_key, type_key)
end
        
local field_count = to_num(ARGV[2])
if field_count == 0 then return 0 end

local data_params = {{}}
local type_params = {{}}

for i = 0, field_count - 1 do
    local offset = 3 + i * 3
    insert(data_params, ARGV[offset])     -- field
    insert(data_params, ARGV[offset + 1]) -- value
    
    insert(type_params, ARGV[offset])     -- field
    insert(type_params, ARGV[offset + 2]) -- type
end

redis_call('HSET', hash_key, unpack(data_params))
redis_call('HSET', type_key, unpack(type_params))

return field_count
"""

_READ_HASH_LUA = f"""
-- v0.0.1
-- Fetches data and types atomically
-- The types are stored in the {_TYPES_COLLECTION} collection under 
-- the same key but prepended with "{_TYPES_COLLECTION}:"
--
-- KEYS[1] = hash_key

local redis_call = redis.call
local hash_key = KEYS[1]
local type_key = "{_TYPES_COLLECTION}:" .. hash_key

local data = redis_call('HGETALL', hash_key)
local types = redis_call('HGETALL', type_key)

return {{data, types}}
"""


class QueryOptions(TypedDict, total=False):
    collection: _Collection
    pk: str
    field: str
    value: _Value


class RedisStoreQueryFunc(Protocol):
    """Matches the fields that should be returned by a query

    It returns true if the value should be added to the resulting
    dictionary of Dict[collection, Dict[pk, Dict[field, _Value]]]
    """

    def __call__(self, opts: QueryOptions) -> bool: ...


class RedisStore:
    """Store to handle persisting and querying data from Redis.

    Layout
    ------
    For each ``(collection, primary_key)`` pair the store keeps two parallel
    hashes:

    * ``{collection}:{primary_key}`` — the canonical hash holding the raw
      stringified field values. This matches the layout used by the legacy
      module-level helpers (:func:`load_redis_config` and friends) so that
      this class can replace them transparently.
    * ``{collection}:{primary_key}:__types__`` — a sidecar hash mapping each
      field to a short python type label (``int``, ``float``, ``list`` ...).
      It exists so that values can be round-tripped back to their original
      python type without resorting to ``eval`` on list reprs.
    """

    def __init__(self, connection: Redis):
        self._connection = connection
        self._save_field_script = connection.register_script(_SAVE_FIELD_LUA)
        self._read_field_script = connection.register_script(_READ_FIELD_LUA)
        self._save_hash_script = connection.register_script(_SAVE_HASH_LUA)
        self._read_hash_script = connection.register_script(_READ_HASH_LUA)

    def save_field(
        self, collection: _Collection, pk: str, field_path: str, value: _Value
    ) -> None:
        """Save a field to Redis.

        Args:
            collection: the collection to save to, options are transmons, couplers, cs.
            pk: the primary key of the object whose field is to be saved.
            field_path: the colon-separated path to the value of the field to be saved.
            value: the value to be saved.
        """
        self._save_field_script(
            keys=[
                self._get_hash_key(collection, pk),
            ],
            args=[field_path, _serialize(value), _get_type_str(value)],
        )

    def read_field(self, collection: _Collection, pk: str, field_path: str) -> _Value:
        """Extract a field from Redis.

        Args:
            collection: the collection to read from, options are transmons, couplers, cs.
            pk: the primary key of the object whose field is to be read.
            field_path: the colon-separated path to the field to be read.

        Returns:
            the value read from redis but parsed back to its python type.
        """
        raw, label = self._read_field_script(
            keys=[
                self._get_hash_key(collection, pk),
            ],
            args=[field_path],
        )
        return _deserialize(raw, label)

    def save_many(self, obj: _RedisStoreObject, reset: bool = False) -> None:
        """Save many records to Redis, with the records nested in their collections

        Args:
            obj: the object to save. It is of format
                ``Mapping[collection, Mapping[primary_key, Mapping[field_name, _Value]]]``
            reset: if ``True`` every primary key in ``obj`` is wiped (the
                canonical hash and its types sidecar are deleted) before the
                new fields are written, yielding a fresh record. If ``False``
                (default) the new fields are merged on top of any pre-existing
                record: fields that share a name are overwritten and the rest
                are left untouched.
        """
        reset_flag = int(reset)

        for collection, record_list in obj.items():
            for pk, record in record_list.items():
                redis_args = list(_to_redis_args(record))
                field_count = len(redis_args) / 2
                hash_key = self._get_hash_key(collection, pk)

                self._save_hash_script(
                    keys=[hash_key],
                    args=[reset_flag, field_count, *redis_args],
                )

    def find_many(
        self,
        collection: Optional[_Collection] = None,
        pks: Optional[Iterable[str]] = None,
        query: Optional[RedisStoreQueryFunc] = None,
    ) -> _RedisStoreObject:
        """Read all objects from Redis matching ``query``.

        Args:
            collection: the collection to read from, options are transmons, couplers, cs.
            pks: the primary keys to look into.
            query: callable ``(collection, primary_key, field, value) -> bool``
                that decides whether a value should appear in the result.

        Returns:
            a dictionary of format
            ``Dict[collection, Dict[primary_key, Dict[field_name, _Value]]]``.
        """
        pattern = _get_scan_pattern(collection=collection, pks=pks)
        result = {}

        for key in self._connection.scan_iter(match=pattern, count=200, _type="HASH"):
            if key.startswith(f"{_TYPES_COLLECTION}:"):
                # Skip all keys that are for types
                continue

            try:
                record = self._find_by_hash_key(key)
                collection, pk = key.split(":", maxsplit=1)
            except (KeyError, ValueError) as e:
                continue

            matched_fields_obj = record
            if query:
                matched_fields_obj = {
                    k: v
                    for k, v in record.items()
                    if query(dict(collection=collection, pk=pk, field=k, value=v))
                }

            if matched_fields_obj:
                insert_nested_key(
                    result, path=(collection, pk), value=matched_fields_obj
                )

        return result

    def find_one(self, collection: _Collection, pk: str) -> Mapping[str, _Value]:
        """Read a single object from Redis collection matching ``pk``.

        Args:
            collection: the collection to read from, options are transmons, couplers, cs.
            pk: the primary key of the object to be read.

        Returns:
            a dictionary of the record of the given ``pk`` or None if it doesn't exist.

        Raises:
            KeyError: if key ``pk`` is not in the collection and ignore_missing is False.
        """
        hash_key = self._get_hash_key(collection, pk)
        try:
            return self._find_by_hash_key(hash_key)
        except KeyError as e:
            raise KeyError(f"Key {pk} not found in collection {collection}") from e

    def _find_by_hash_key(self, hash_key: str) -> Mapping[str, _Value]:
        """Reads the single record whose hash key matches ``hash_key``.

        Args:
            hash_key: the hash key to look into.

        Returns:
            the record as a dictionary

        Raises:
            KeyError: if record of the given hash key doesn't exist.
        """
        raw_data, raw_types = self._read_hash_script(keys=[hash_key])

        if not raw_data:
            raise KeyError(f"Key {hash_key} not found")

        return _from_redis_values(raw_data=raw_data, raw_types=raw_types)

    @staticmethod
    def _get_hash_key(collection: _Collection, pk: str) -> str:
        """Returns the canonical hash key for ``(collection, pk)``."""
        return f"{collection}:{pk}"


def qoi_to_redis_record(
    qoi: QOI = None,
    redis_fields: List[str] = (),
) -> Dict[str, _Value]:
    """Converts the quantity of interest (QOI) into a redis record

    Args:
        qoi: The quantity of interest as QOI wrapped object
        redis_fields: List of redis fields that are allowed for this QOI

    Returns:
        the record that would be saved in redis for this QOI
    """
    results = qoi.analysis_result
    rogue_fields = results.keys() - set(redis_fields)
    if rogue_fields:
        raise ValueError(
            f"The QOI's {rogue_fields} are not in redis fields: {redis_fields}"
        )

    record = {}
    for k, res in results.items():
        record[k] = res["value"]
        record[f"{k}_error"] = res["error"]

    return record


def _get_key_segments(key: str, expected_count: int = 2) -> Tuple[str, ...]:
    """Get key's segments, as separated by ``:``

    Args:
        key: the key to look into.
        expected_count: the expected number of segments.

    Returns:
        the key's segments as tuple

    Raises:
        ValueError: if the segments are not the expected number of segments.
    """


def _get_type_str(value: Any) -> str:
    """Returns a short python type label for ``value``."""
    for tp, label in _TYPE_LABELS.items():
        if isinstance(value, tp):
            return label
    return "str"


def _get_scan_pattern(
    collection: Optional[_Collection] = None, pks: Optional[Iterable[str]] = None
) -> str:
    """Returns the scan glob pattern given collection and primary keys.

    Args:
        collection: the collection to get scan pattern from.
        pks: the primary keys to look into.

    Returns:
        the glob pattern to use in redis SCAN
    """
    if not collection:
        collection = "*"

    if pks and len(pks) == 1:
        return f"{collection}:{pks[0]}"

    # return the records for all
    if collection == "*":
        return "*"

    return f"{collection}:*"


def _serialize(value: Any) -> str:
    """Encode ``value`` as a redis-friendly string.

    Scalars use their natural ``str(...)`` form so that legacy code which
    runs e.g. ``float(redis_value)`` keeps working unchanged. Collections
    use JSON which can be parsed back without resorting to ``eval``.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value))
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


def _deserialize(raw: Any, label: Any) -> Any:
    """Inverse of :func:`_serialize`.

    Missing or unknown labels fall back to returning the raw decoded string
    so that hashes written via the legacy helpers can still be read. Lists
    written via ``str(list_value)`` (legacy format) are recovered using
    :func:`ast.literal_eval` as a backup.
    """
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(label, bytes):
        label = label.decode("utf-8")

    if label == "int":
        return int(raw)
    if label == "float":
        return float(raw)
    if label == "bool":
        return raw not in ("0", "False", "false", "")
    if label == "none":
        return None
    if label in ("list", "dict"):
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return ast.literal_eval(raw)

    # deal with the values saved prior to this store
    with suppress(json.JSONDecodeError):
        return json.loads(raw)

    return raw


def _to_redis_args(value: Mapping[str, Any], key_prefix: str = "") -> Iterator[str]:
    """Flatten a nested dictionary into a flat iterator of field_path, value, type redis args

    The field_paths are demarcated by colons when nested
    The returned iterator is of form [field_path_1, value_1, type_1, field_path_2, value_2, type_2, ... ]

    Args:
        key_prefix: the prefix to insert before the keys
        value: The dictionary to flatten.

    Returns:
        The iterator.
    """
    for k, v in value.items():
        key = f"{key_prefix}{k}"
        if isinstance(v, MappingABC):
            yield from _to_redis_args(v, f"{key}:")
        else:
            yield from (key, _serialize(v), _get_type_str(v))


def _from_redis_values(raw_data: List[str], raw_types: List[str]) -> Dict[str, _Value]:
    """Creates a dictionary from the raw data and raw types passed from redis

    The raw data and keys are of the form [k1, v1, k2, v2]

    Args:
        raw_data: the data that as got from redis in its flat form of [k1, v1, k2, v2]
        raw_types: the types list as got from redis in its flat form of [k1, v1, k2, v2].

    Returns:
        The parsed record as a dict.
    """
    # Convert flat [k1, v1, k2, v2] list to {k1: v1, k2: v2}
    type_dict = dict(zip(raw_types[::2], raw_types[1::2]))

    result = {}
    # Convert flat [k1, v1, k2, v2] list to {k1: {k1_1: v1}, k2: v2}
    for k, v in zip(raw_data[::2], raw_data[1::2]):
        value = _deserialize(v, type_dict.get(k))
        path = tuple(k.split(":"))
        insert_nested_key(result, path=path, value=value)

    return result
