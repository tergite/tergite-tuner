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

import json
import tomllib
from os import PathLike
from pathlib import Path

from pydantic import BaseModel


def load_config[ModelT: BaseModel](
    model: type[ModelT], path: str | PathLike[str]
) -> ModelT:
    """The ``model`` in the file at ``path``: JSON for a ``.json`` file, TOML otherwise.

    Args:
        model: the pydantic model the file holds.
        path: the file.

    Returns:
        The validated model.

    Raises:
        pydantic.ValidationError: if the file does not match the model.
    """
    path = Path(path)
    if path.suffix == ".json":
        data = json.loads(path.read_text())
    else:
        with path.open("rb") as file:
            data = tomllib.load(file)
    return model.model_validate(data)
