# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for :class:`tergite_tuner.lib.utils.redis.RedisStore`.

The suite covers per-type round-tripping, the layout contract that lets the
store drop in for the legacy ``_save_parameters_*`` helpers, and the merge /
reset semantics of ``save_many``.
"""

import ast
from typing import Any, Dict, Literal

import pytest

from tergite_tuner.lib.utils.redis import RedisStore
from tergite_tuner.utils.dto.qoi import QOI

_ROUND_TRIP_VALUES = [
    0,
    42,
    -7,
    0.0,
    3.14,
    -1.5e-9,
    4.2e9,
    True,
    False,
    "",
    "calibrated",
    "with:colon:in:value",
    [],
    [1.0, 2.0, 3.5],
    [1, 2, 3],
    ["a", "b", "c"],
    {"k": "v"},
    {"nested": {"a": 1.0, "b": 2.0}},
    None,
]


@pytest.fixture
def store(redis_connection) -> RedisStore:
    """A :class:`RedisStore` bound to the project's fakeredis fixture."""
    return RedisStore(redis_connection)


def test_save_parameters_in_transmon_via_redis_store(redis_connection, store):
    """Replacement for the legacy ``_save_parameters_in_transmon`` test:
    save the resonator-spectroscopy QOI for a single transmon through the
    RedisStore API and verify that both the store and a raw ``hget`` (the
    contract that lets the store drop in for the legacy helpers) see the
    expected values."""
    qubit = "q01"
    redis_fields = ["resonator_minimum"]
    qoi = QOI(
        analysis_result={
            "resonator_minimum": {"value": 3.91e9, "error": 0.01},
        },
        analysis_successful=True,
    )

    fields: dict = {}
    for name, result in qoi.analysis_result.items():
        assert name in redis_fields
        fields[name] = result["value"]
        fields[f"{name}_error"] = result["error"]
    store.save_many({"transmons": {qubit: fields}})
    store.save_field("cs", qubit, "resonator_spectroscopy", "calibrated")

    assert store.read_field("transmons", qubit, "resonator_minimum") == 3.91e9
    assert store.read_field("transmons", qubit, "resonator_minimum_error") == 0.01
    assert store.read_field("cs", qubit, "resonator_spectroscopy") == "calibrated"

    assert (
        float(redis_connection.hget(f"transmons:{qubit}", "resonator_minimum"))
        == 3.91e9
    )
    assert (
        float(redis_connection.hget(f"transmons:{qubit}", "resonator_minimum_error"))
        == 0.01
    )
    assert (
        redis_connection.hget(f"cs:{qubit}", "resonator_spectroscopy") == "calibrated"
    )


@pytest.mark.parametrize("value", _ROUND_TRIP_VALUES)
def test_save_field_round_trip(store, value):
    """Every supported python type round-trips through redis unchanged."""
    store.save_field("transmons", "q01", "field_x", value)
    assert store.read_field("transmons", "q01", "field_x") == value


def test_read_field_returns_none_for_missing_field(store):
    """An unset field reads back as ``None`` rather than raising."""
    assert store.read_field("transmons", "q01", "no_such_field") is None


def test_save_field_records_correct_type_label(redis_connection, store):
    """Each save writes a corresponding entry in the types sidecar so the
    value can be deserialized to its original python type later."""
    store.save_field("transmons", "q01", "freq", 4.2e9)
    store.save_field("transmons", "q01", "channel", 7)
    store.save_field("transmons", "q01", "is_active", True)
    store.save_field("transmons", "q01", "freq_list", [1.0, 2.0])
    store.save_field("transmons", "q01", "name", "q01")
    labels = redis_connection.hgetall("__types__:transmons:q01")
    assert labels == {
        "freq": "float",
        "channel": "int",
        "is_active": "bool",
        "freq_list": "list",
        "name": "str",
    }


def test_int_and_float_keep_their_types(store):
    """Integers stay ``int`` and floats stay ``float`` after a round-trip;
    they are not collapsed to a single numeric type."""
    store.save_field("transmons", "q01", "channel", 7)
    store.save_field("transmons", "q01", "freq", 7.0)
    channel = store.read_field("transmons", "q01", "channel")
    freq = store.read_field("transmons", "q01", "freq")
    assert isinstance(channel, int) and channel == 7
    assert isinstance(freq, float) and freq == 7.0


def test_canonical_hash_has_no_types_pollution(redis_connection, store):
    """The canonical hash holds only user-written fields; legacy callers can
    still iterate it with ``hgetall`` and parse values with ``float(...)``."""
    store.save_field("transmons", "q01", "clock_freqs:f01", 4.2e9)
    store.save_field("transmons", "q01", "clock_freqs:f12", 3.9e9)
    raw = redis_connection.hgetall("transmons:q01")
    assert set(raw) == {"clock_freqs:f01", "clock_freqs:f12"}
    assert {k: float(v) for k, v in raw.items()} == {
        "clock_freqs:f01": 4.2e9,
        "clock_freqs:f12": 3.9e9,
    }


def test_types_sidecar_lives_in_a_separate_hash(redis_connection, store):
    """Type labels are stored in a parallel ``__types__:...`` hash, never
    mixed into the canonical hash itself."""
    store.save_field("couplers", "q01_q02", "freqs", [1.0, 2.0, 3.5])
    sidecar = redis_connection.hgetall("__types__:couplers:q01_q02")
    assert sidecar == {"freqs": "list"}
    canonical = redis_connection.hgetall("couplers:q01_q02")
    assert "__types__" not in canonical


def test_list_written_via_store_is_legacy_literal_eval_safe(redis_connection, store):
    """Lists written through the store use JSON, but the JSON encoding of
    numeric/string lists is also ``ast.literal_eval``-friendly so existing
    legacy readers keep working unchanged."""
    store.save_field("couplers", "q01_q02", "freqs", [1.0, 2.0, 3.5])
    raw = redis_connection.hget("couplers:q01_q02", "freqs")
    assert ast.literal_eval(raw) == [1.0, 2.0, 3.5]


def test_legacy_str_list_value_reads_back_via_literal_eval_fallback(
    redis_connection, store
):
    """Legacy writers produced ``str([...])`` blobs and never wrote a types
    sidecar. Once a ``list`` label is attached the value can be recovered:
    ``_deserialize`` falls back to ``ast.literal_eval`` when JSON decoding of
    the legacy string fails."""
    redis_connection.hset("couplers:legacy", "freqs", "[1, 2, 3]")
    redis_connection.hset("__types__:couplers:legacy", "freqs", "list")
    assert store.read_field("couplers", "legacy", "freqs") == [1, 2, 3]


def test_legacy_value_without_types_sidecar_reads_as_raw_string(
    redis_connection, store
):
    """When no types sidecar exists ``read_field`` automatically parses the value."""
    redis_connection.hset("couplers:legacy", "freqs", "[1, 2, 3]")
    assert store.read_field("couplers", "legacy", "freqs") == [1, 2, 3]


def test_save_many_default_merges_into_existing_pk(store):
    """The default ``reset=False`` overwrites same-named fields, adds new
    fields, and leaves untouched fields in place."""
    store.save_many(
        {
            "transmons": {
                "q01": {
                    "clock_freqs:f01": 4.2e9,
                    "clock_freqs:f12": 3.9e9,
                }
            }
        }
    )
    store.save_many(
        {
            "transmons": {
                "q01": {
                    "clock_freqs:f01": 9.9e9,
                    "extra_field": 1.0,
                }
            }
        }
    )
    assert store.read_field("transmons", "q01", "clock_freqs:f01") == 9.9e9
    assert store.read_field("transmons", "q01", "clock_freqs:f12") == 3.9e9
    assert store.read_field("transmons", "q01", "extra_field") == 1.0


def test_save_many_reset_wipes_pk_before_writing(redis_connection, store):
    """``reset=True`` deletes both the canonical hash and its types sidecar
    before writing, so stale fields and their type labels are gone."""
    store.save_many(
        {
            "transmons": {
                "q01": {
                    "clock_freqs:f01": 4.2e9,
                    "clock_freqs:f12": 3.9e9,
                }
            }
        }
    )
    store.save_many({"transmons": {"q01": {"only": 1.0}}}, reset=True)
    assert store.read_field("transmons", "q01", "only") == 1.0
    assert store.read_field("transmons", "q01", "clock_freqs:f01") is None
    assert store.read_field("transmons", "q01", "clock_freqs:f12") is None
    assert redis_connection.hgetall("__types__:transmons:q01") == {"only": "float"}


def test_save_many_reset_only_affects_listed_pks(store):
    """``reset=True`` only resets the primary keys passed in this call; other
    pks in the same collection are left alone."""
    store.save_many({"transmons": {"q01": {"x": 1.0}, "q02": {"x": 2.0}}})
    store.save_many({"transmons": {"q01": {"new": 7.0}}}, reset=True)
    assert store.read_field("transmons", "q02", "x") == 2.0
    assert store.read_field("transmons", "q01", "x") is None
    assert store.read_field("transmons", "q01", "new") == 7.0


def test_save_many_with_no_fields_does_not_create_a_phantom_hash(
    redis_connection, store
):
    """Passing an empty fields dict is a no-op: no canonical or sidecar hash
    is created."""
    store.save_many({"transmons": {"q01": {}}})
    assert redis_connection.exists("transmons:q01") == 0
    assert redis_connection.exists("transmons:q01:__types__") == 0


def test_save_many_handles_multiple_collections(store):
    """A single ``save_many`` call writes across all three collections."""
    store.save_many(
        {
            "transmons": {"q01": {"freq": 4.2e9}},
            "couplers": {"q01_q02": {"cz_freq": 100e6}},
            "cs": {"q01": {"resonator_spectroscopy": "calibrated"}},
        }
    )
    assert store.read_field("transmons", "q01", "freq") == 4.2e9
    assert store.read_field("couplers", "q01_q02", "cz_freq") == 100e6
    assert store.read_field("cs", "q01", "resonator_spectroscopy") == "calibrated"


def test_find_many_filters_by_query(store):
    """``find_many`` returns only the (collection, pk, field, value) tuples
    for which the query callable returns ``True``."""
    store.save_many(
        {
            "transmons": {
                "q01": {"clock_freqs:f01": 4.2e9, "name": "q01"},
                "q02": {"clock_freqs:f01": 5.0e9, "name": "q02"},
            },
            "cs": {"q01": {"resonator_spectroscopy": "calibrated"}},
        }
    )
    out = store.find_many(
        query=lambda opts: opts["collection"] == "transmons"
        and opts["field"].startswith("clock_freqs")
    )
    assert out == {
        "transmons": {
            "q01": {"clock_freqs": {"f01": 4.2e9}},
            "q02": {"clock_freqs": {"f01": 5.0e9}},
        }
    }


def test_find_many_filters_by_collection(store):
    """``find_many`` can filter by collection when collection param is passed."""
    data: Dict[Literal["transmons", "cs"], Dict[str, Any]] = {
        "transmons": {
            "q01": {"clock_freqs:f01": 4.2e9, "name": "q01"},
            "q02": {"clock_freqs:f01": 5.0e9, "name": "q02"},
        },
        "cs": {"q01": {"resonator_spectroscopy": "calibrated"}},
    }
    store.save_many(data)
    out = store.find_many(collection="transmons")
    assert out == {
        "transmons": {
            "q01": {"clock_freqs": {"f01": 4.2e9}, "name": "q01"},
            "q02": {"clock_freqs": {"f01": 5.0e9}, "name": "q02"},
        }
    }
    out = store.find_many(collection="cs")
    assert out == {"cs": out["cs"]}


def test_find_many_filters_by_pks(store):
    """``find_many`` can filter by pks when pks param is given."""
    data: Dict[Literal["transmons", "cs", "couplers"], Dict[str, Any]] = {
        "transmons": {
            "q01": {"clock_freqs:f01": 4.2e9, "name": "q01"},
            "q02": {"clock_freqs:f01": 5.0e9, "name": "q02"},
        },
        "cs": {"q01": {"resonator_spectroscopy": "calibrated"}},
        "couplers": {
            "q01": {"clock_freqs:f01": 4.2e9, "name": "q01"},
        },
    }
    store.save_many(data)
    out = store.find_many(pks=("q01",))
    assert out == {
        "transmons": {
            "q01": {"clock_freqs": {"f01": 4.2e9}, "name": "q01"},
        },
        "cs": data["cs"],
        "couplers": {
            "q01": {"clock_freqs": {"f01": 4.2e9}, "name": "q01"},
        },
    }
    out = store.find_many(pks=("q02",))
    assert out == {
        "transmons": {
            "q02": {"clock_freqs": {"f01": 5.0e9}, "name": "q02"},
        }
    }


def test_find_many_filters_by_pks_collection_and_query(store):
    """``find_many`` can filter by pks when pks param is given and query and collection param."""
    data: Dict[Literal["transmons", "cs", "couplers"], Dict[str, Any]] = {
        "transmons": {
            "q01": {"clock_freqs:f01": 4.2e9, "name": "q01"},
            "q02": {"clock_freqs:f01": 5.0e9, "name": "q02"},
        },
        "cs": {"q01": {"resonator_spectroscopy": "calibrated"}},
        "couplers": {
            "q01": {"clock_freqs:f01": 4.2e9, "name": "q01"},
        },
    }
    store.save_many(data)
    out = store.find_many(
        pks=("q01",),
        collection="transmons",
        query=lambda opts: (
            False
            if not isinstance(opts["value"], dict)
            else opts["value"]["f01"] == 4.2e9
        ),
    )
    assert out == {"transmons": {"q01": {"clock_freqs": {"f01": 4.2e9}}}}


def test_find_many_returns_typed_values(store):
    """Values come back already coerced to their original python types."""
    store.save_many(
        {
            "transmons": {
                "q01": {
                    "freq": 4.2e9,
                    "channel": 7,
                    "is_active": True,
                    "freq_list": [1.0, 2.0],
                    "name": "q01",
                }
            }
        }
    )
    out = store.find_many(query=lambda *_: True)
    fields = out["transmons"]["q01"]
    assert fields["freq"] == 4.2e9 and isinstance(fields["freq"], float)
    assert fields["channel"] == 7 and isinstance(fields["channel"], int)
    assert fields["is_active"] is True
    assert fields["freq_list"] == [1.0, 2.0]
    assert fields["name"] == "q01"


def test_find_many_empty_query_returns_empty_result(store):
    """A query that always returns ``False`` yields an empty result."""
    store.save_field("transmons", "q01", "freq", 4.2e9)
    out = store.find_many(query=lambda *_: False)
    assert out == {}


def test_find_many_skips_types_sidecar_keys(store):
    """The result must contain the canonical pk only, never a phantom one
    such as ``q01:__types__`` produced by the sidecar bookkeeping."""
    store.save_field("transmons", "q01", "freq", 4.2e9)
    out = store.find_many(query=lambda *_: True)
    assert list(out["transmons"].keys()) == ["q01"]


def test_find_many_handles_compound_pk(store):
    """The qubits-in-coupler layout uses ``couplers:<bus>:<qubit>``; the
    primary key in that case is ``"<bus>:<qubit>"`` (with the colon)."""
    store.save_many(
        {
            "transmons": {
                "q01": {
                    "freq": 4.2e9,
                    "channel": 7,
                    "is_active": True,
                    "freq_list": [1.0, 2.0],
                    "name": "q01",
                }
            },
            "couplers": {
                "q01_q02:q01": {"freq": 4.2e9},
                "q01_q02:q02": {"freq": 4.3e9},
            },
        }
    )
    out = store.find_many(query=lambda opts: opts["collection"] == "couplers")
    assert out == {
        "couplers": {
            "q01_q02:q01": {"freq": 4.2e9},
            "q01_q02:q02": {"freq": 4.3e9},
        }
    }


def test_find_many_returns_empty_when_no_data(store):
    """``find_many`` against a fresh redis returns ``{}``."""
    assert store.find_many(lambda *_: True) == {}
