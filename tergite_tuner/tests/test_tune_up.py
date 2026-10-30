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


import pytest

from tergite_tuner.tests.utils.runs import DEFAULT_NODES, run_dummy_node
from tergite_tuner.utils.types.node_enum import NodeEnum


@pytest.mark.slow
@pytest.mark.parametrize("node", DEFAULT_NODES, ids=lambda node: node.value)
def test_every_default_node_runs_in_dummy_mode(
    node, session_context, tmp_path, monkeypatch
):
    # the dummy cluster assembles in the working directory, which workers would share
    monkeypatch.chdir(tmp_path)
    run_dummy_node(node, session_context, tmp_path)

    # analyses of random IQ points may fail; reaching them without raising is the check
    assert list(tmp_path.glob(f"*-run/dataset_{node.value}.hdf5"))


def test_unkept_data_files_delete_only_the_runs_folder(
    session_context, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "out"
    earlier_file = data_dir / "earlier" / "dataset.hdf5"
    earlier_file.parent.mkdir(parents=True)
    earlier_file.touch()

    run_dummy_node(
        NodeEnum.RESONATOR_SPECTROSCOPY,
        session_context,
        data_dir,
        keep_data_files=False,
    )

    assert sorted(data_dir.rglob("*")) == [earlier_file.parent, earlier_file]
