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
import re
from typing import Any, Callable, Dict, List, Literal, Mapping, TypeVar, Union

import numpy as np
from quantify_scheduler.json_utils import SchedulerJSONDecoder, SchedulerJSONEncoder
from redis import Redis

from tergite_tuner.utils.dto import extended_transmon_element
from tergite_tuner.utils.dto.extended_coupler_edge import ExtendedCompositeSquareEdge
from tergite_tuner.utils.dto.extended_transmon_element import ExtendedTransmon
from tergite_tuner.utils.dto.qoi import QOI
from tergite_tuner.utils.logging import logger

np.set_printoptions(legacy="1.25")

_Value = TypeVar("_Value", bound=Union[str, float, int, bool, list, dict, None])
_Collection = Literal["transmons", "couplers", "cs"]
_QueryFunc = Callable[[_Collection, str, str, Any], bool]
"""(collection, primary_key, field_name, value) -> bool

It returns true if the value should be added to the resulting
dictionary of Dict[collection, Dict[primary_key, Dict[field_name, _Value]]]
"""

# All known collections. Used by ``RedisStore.read_object`` to limit the
# keyspace scan to namespaces this store owns.
_COLLECTIONS: tuple = ("transmons", "couplers", "cs")

# Suffix appended to a canonical hash key to form a sidecar hash that holds
# the python type label of each field. Living alongside the canonical hash
# means legacy callers using e.g. ``hgetall("transmons:q01")`` keep seeing a
# clean payload.
_TYPES_SUFFIX = "__types__"

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


class RedisStore[_Value]:
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

    # Atomically write a field's value and its type label so the canonical
    # hash and its sidecar can never get out of sync.
    _SAVE_FIELD_LUA = """
        redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
        redis.call('HSET', KEYS[2], ARGV[1], ARGV[3])
        return 1
    """

    # Atomically read a field's value and its type label.
    _READ_FIELD_LUA = """
        local value = redis.call('HGET', KEYS[1], ARGV[1])
        local label = redis.call('HGET', KEYS[2], ARGV[1])
        return {value, label}
    """

    # Bulk-write every field of a single primary key. ARGV layout:
    #   [reset_flag, field_count, field_1, value_1, label_1, ...]
    # When ``reset`` is 1 the canonical hash and its sidecar are deleted
    # before the new fields are written, yielding a fresh record. When
    # ``reset`` is 0 the writes are merged on top of any pre-existing
    # record: fields that share a name are overwritten, the rest are left
    # untouched.
    _SAVE_HASH_LUA = """
        local reset = tonumber(ARGV[1])
        if reset == 1 then
            redis.call('DEL', KEYS[1])
            redis.call('DEL', KEYS[2])
        end
        local count = tonumber(ARGV[2])
        for i = 0, count - 1 do
            local field = ARGV[3 + i * 3]
            local value = ARGV[4 + i * 3]
            local label = ARGV[5 + i * 3]
            redis.call('HSET', KEYS[1], field, value)
            redis.call('HSET', KEYS[2], field, label)
        end
        return count
    """

    def __init__(self, connection: Redis):
        self._connection = connection
        self._save_field_script = connection.register_script(self._SAVE_FIELD_LUA)
        self._read_field_script = connection.register_script(self._READ_FIELD_LUA)
        self._save_hash_script = connection.register_script(self._SAVE_HASH_LUA)

    def save_field(
        self, collection: _Collection, pk: str, field: str, value: _Value
    ) -> None:
        """Save a field to Redis.

        Args:
            collection: the collection to save to, options are transmons, couplers, cs.
            pk: the primary key of the object whose field is to be saved.
            field: the name of the field to be saved.
            value: the value to be saved.
        """
        self._save_field_script(
            keys=[
                self._get_hash_key(collection, pk),
                self._get_types_key(collection, pk),
            ],
            args=[field, _serialize(value), _label_for(value)],
        )

    def read_field(self, collection: _Collection, pk: str, field: str) -> _Value:
        """Load a field from Redis.

        Args:
            collection: the collection to read from, options are transmons, couplers, cs.
            pk: the primary key of the object whose field is to be read.
            field: the name of the field to be read.

        Returns:
            the value read from redis but parsed back to its python type.
        """
        raw, label = self._read_field_script(
            keys=[
                self._get_hash_key(collection, pk),
                self._get_types_key(collection, pk),
            ],
            args=[field],
        )
        return _deserialize(raw, label)

    def save_object(
        self,
        obj: Mapping[_Collection, Mapping[str, Mapping[str, _Value]]],
        reset: bool = False,
    ) -> None:
        """Save an object to Redis.

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
        for collection, by_pk in obj.items():
            for pk, fields in by_pk.items():
                args: List[Any] = [1 if reset else 0, len(fields)]
                for field, value in fields.items():
                    args.extend([field, _serialize(value), _label_for(value)])
                self._save_hash_script(
                    keys=[
                        self._get_hash_key(collection, pk),
                        self._get_types_key(collection, pk),
                    ],
                    args=args,
                )

    def read_object(
        self, query: _QueryFunc
    ) -> Dict[_Collection, Dict[str, Dict[str, _Value]]]:
        """Read all objects from Redis matching ``query``.

        Args:
            query: callable ``(collection, primary_key, field_name, value) -> bool``
                that decides whether a tuple should appear in the result.

        Returns:
            a dictionary of format
            ``Dict[collection, Dict[primary_key, Dict[field_name, _Value]]]``.
        """
        result: Dict[_Collection, Dict[str, Dict[str, _Value]]] = {}
        for collection in _COLLECTIONS:
            pattern = f"{collection}:*"
            for raw_key in self._connection.scan_iter(match=pattern, count=200):
                key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else raw_key
                # Sidecar ``__types__`` hashes are bookkeeping; skip them.
                if key.endswith(f":{_TYPES_SUFFIX}"):
                    continue
                pk = key[len(collection) + 1 :]
                raw_fields = self._connection.hgetall(key)
                if not raw_fields:
                    continue
                raw_labels = self._connection.hgetall(
                    self._get_types_key(collection, pk)
                )
                for raw_field, raw_value in raw_fields.items():
                    field = (
                        raw_field.decode("utf-8")
                        if isinstance(raw_field, bytes)
                        else raw_field
                    )
                    label = raw_labels.get(raw_field) or raw_labels.get(field)
                    value = _deserialize(raw_value, label)
                    if query(collection, pk, field, value):
                        result.setdefault(collection, {}).setdefault(pk, {})[
                            field
                        ] = value
        return result

    @staticmethod
    def _get_hash_key(collection: _Collection, pk: str) -> str:
        """Returns the canonical hash key for ``(collection, pk)``."""
        return f"{collection}:{pk}"

    @staticmethod
    def _get_types_key(collection: _Collection, pk: str) -> str:
        """Returns the types sidecar hash key for ``(collection, pk)``."""
        return f"{collection}:{pk}:{_TYPES_SUFFIX}"


def _label_for(value: Any) -> str:
    """Returns a short python type label for ``value``."""
    for tp, label in _TYPE_LABELS.items():
        if isinstance(value, tp):
            return label
    return "str"


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
    return raw


def load_redis_config(transmon: ExtendedTransmon, channel: int, redis_connection):
    qubit = transmon.name
    redis_config = redis_connection.hgetall(f"transmons:{qubit}")

    # get the transmon template in dictionary form
    serialized_transmon = json.dumps(transmon, cls=SchedulerJSONEncoder)
    decoded_transmon = json.loads(serialized_transmon)

    # the transmon modules are recognized by the ':' in the redis key
    transmon_redis_config = {k: v for k, v in redis_config.items() if ":" in k}
    device_redis_dict = {}
    for redis_entry_key, redis_value in transmon_redis_config.items():
        redis_value = float(redis_value)
        # e.g. 'clock_freqs:f01' is split to clock_freqs, f01
        submodule, field = redis_entry_key.split(":")
        device_redis_dict[submodule] = device_redis_dict.get(submodule, {}) | {
            field: redis_value
        }

    device_redis_dict["name"] = qubit

    for submodule in decoded_transmon["data"]:
        sub_module_content = decoded_transmon["data"][submodule]
        if isinstance(sub_module_content, dict) and submodule in device_redis_dict:
            redis_module_config = device_redis_dict[submodule]
            decoded_transmon["data"][submodule].update(redis_module_config)
        if "measure" in submodule:
            decoded_transmon["data"][submodule].update({"acq_channel": channel})

    encoded_transmon = json.dumps(decoded_transmon)

    # free the transmon
    transmon.close()

    # create a transmon with the same name but with updated config
    transmon = json.loads(
        encoded_transmon, cls=SchedulerJSONDecoder, modules=[extended_transmon_element]
    )

    return transmon


def load_redis_config_coupler(coupler: ExtendedCompositeSquareEdge, redis_connection):
    bus = coupler.name
    bus_qubits = bus.split("_")
    redis_config = redis_connection.hgetall(f"couplers:{bus}")

    def redis_value(key: str):
        return float(redis_config[key])

    key = "cz_pulse_frequency"
    try:
        coupler.clock_freqs.cz_freq(redis_value(key))
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )
    key = "cz_pulse_amplitude"
    try:
        coupler.cz.square_amp(redis_value(key))
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )
    key = "cz_pulse_duration"
    try:
        coupler.cz.square_duration(redis_value(key))
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )
    key = "cz_half_duration"
    try:
        coupler.cz.half_square_duration(redis_value(key))
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )
    key = "cz_pulse_width"
    try:
        coupler.cz.cz_width(redis_value(key))
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )
    key = "parking_current"
    try:
        coupler.coupler_parameters.parking_current(redis_value(key))
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )
    key = "initial_parking_current"
    try:
        coupler.coupler_parameters.parking_current(redis_value(key))
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )
    try:
        if bus_qubits[0] == str(redis_config["target_qubit"]):
            logger.info(f"Reading Target Qubit from Redis: {bus_qubits[0]}")
            # coupler.cz.parent_phase_correction(redis_value("target_local_phase"))
            # coupler.cz.child_phase_correction(redis_value("control_local_phase"))
            coupler.cz.parent_phase_correction(redis_value("cz_dynamic_target"))
            coupler.cz.child_phase_correction(redis_value("cz_dynamic_control"))

        elif bus_qubits[0] == str(redis_config["control_qubit"]):
            logger.info(f"Reading Control Qubit from Redis: {bus_qubits[0]}")
            # coupler.cz.parent_phase_correction(redis_value("control_local_phase"))
            # coupler.cz.child_phase_correction(redis_value("target_local_phase"))
            coupler.cz.parent_phase_correction(redis_value("cz_dynamic_control"))
            coupler.cz.child_phase_correction(redis_value("cz_dynamic_target"))

        else:
            raise ValueError("Control - Target types not defined")
    except:
        logger.warning("Invalid Control and Target")
    key = "cz_phase_path"
    try:
        coupler.coupler_parameters.phase_path(redis_config[key])
    except:
        logger.warning(
            f"{key} is not present in redis. Ignore this for single qubit nodes"
        )

    return coupler


def update_redis_trusted_values(
    node: str,
    this_element: str,
    redis_connection,
    qoi: QOI = None,
    redis_fields: Union[List[str], None] = None,
):
    """
    Update the redis trusted values for the qubit or coupler.
    Args:
        node: The node name
        this_element: The element name (qubit or coupler)
        redis_connection: The redis client to write to.
        qoi: The quantity of interest as QOI wrapped object
        redis_fields: List of redis fields for additional verification
    """

    if "_" in this_element:
        name = "couplers"
        _qoi_items = dict(qoi.analysis_result.items())
        if _are_two_qubit_in_qoi(_qoi_items):
            _save_parameters_in_qubits_in_coupler(
                node, this_element, name, _qoi_items, redis_fields, redis_connection
            )
        else:
            _save_parameters_in_coupler(
                node, this_element, name, qoi, redis_fields, redis_connection
            )

    else:
        name = "transmons"
        _save_parameters_in_transmon(
            node, this_element, name, qoi, redis_fields, redis_connection
        )


def _are_two_qubit_in_qoi(qoi: dict):
    return all(re.fullmatch(r"q\d{2}", key) for key in qoi)


def _save_parameters_in_transmon(
    node: str,
    this_element: str,
    name,
    qoi: QOI,
    redis_fields: List[str],
    redis_connection,
):
    """
    Saves the parameters for a single qubit in redis

    Args:
        node: Name of the node to update
        this_element: Name of the element to update, this will be e.g. q01
        name: Name of the property to update e.g. the qubit frequency
        qoi: The QOI object with the value to update
        redis_fields: redis fields from the node to be updated, this is for verification
        redis_connection: redis client to write to.

    Raises:
        ValueError: if there are parameters in the qubit object that are not part of the node

    """
    analysis_successful = qoi.analysis_successful
    if analysis_successful:
        for qoi_name, qoi_result in qoi.analysis_result.items():
            if qoi_name not in redis_fields:
                raise ValueError(
                    f"The qoi {qoi_name} is not in redis fields: {redis_fields} for {this_element}"
                )
            value = qoi_result["value"]
            redis_connection.hset(f"{name}:{this_element}", qoi_name, value)
            # Saving the error to the measured value
            error = qoi_result["error"]
            redis_connection.hset(f"{name}:{this_element}", qoi_name + "_error", error)

        redis_connection.hset(f"cs:{this_element}", node, "calibrated")

    else:
        logger.warning(f"Analysis failed for {this_element}")


def _save_parameters_in_coupler(
    node: str,
    this_element: str,
    name: str,
    qoi: QOI,
    redis_fields: List[str],
    redis_connection,
):
    """
    Saves the parameters for a coupler in redis

    Args:
        node: Name of the node to update
        this_element: Name of the element to update, this will be e.g. q01_q02 for the coupler
        name: Name of the property to update e.g. the dc current
        qoi: The QOI object with the value to update
        redis_fields: redis fields from the node to be updated, this is for verification
        redis_connection: redis client to write to.

    Raises:
        ValueError: if there are parameters in the qubit object that are not part of the node

    """

    analysis_successful = qoi.analysis_successful
    if analysis_successful:
        for qoi_name, qoi_result in qoi.analysis_result.items():
            if qoi_name not in redis_fields:
                raise ValueError(
                    f"The qoi {qoi_name} is not in redis fields: {redis_fields} for {this_element}"
                )
            value = qoi_result["value"]
            if isinstance(value, list):
                value = str(value)
            logger.info(f"Updating redis for {this_element} with {qoi_name}: {value}")
            redis_connection.hset(f"{name}:{this_element}", qoi_name, value)
            error = qoi_result["error"]
            logger.info(
                f"Updating redis for {this_element} with {qoi_name}_error: {error}"
            )
            redis_connection.hset(f"{name}:{this_element}", qoi_name + "_error", error)

    redis_connection.hset(f"cs:{this_element}", node, "calibrated")


def _save_parameters_in_qubits_in_coupler(
    node: str,
    this_element: str,
    name: str,
    qoi: dict,
    redis_fields: List[str],
    redis_connection,
):
    """
    Saves the parameters for the qubits connected to a coupler, in redis

    Args:
        node: Name of the node to update
        this_element: Name of the element to update, this will be e.g. q01_q02,
        the qubits are extracted inside the function
        name: Name of the property to update e.g. the qubit frequency
        qoi: A dictionary that maps from qubit to the respective QOI
        redis_fields: redis fields from the node to be updated, this is for verification
        redis_connection: redis client to write to.

    """

    qubits_in_coupler = [this_element[0:3], this_element[4:7]]
    for qubit in qubits_in_coupler:
        for transmon_parameter in redis_fields:
            redis_connection.hset(
                f"{name}:{this_element}:{qubit}",
                transmon_parameter,
                qoi[qubit][transmon_parameter],
            )

    redis_connection.hset(f"cs:{this_element}", node, "calibrated")
