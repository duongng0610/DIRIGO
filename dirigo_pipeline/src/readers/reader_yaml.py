import yaml
from pathlib import Path
from typing import Any


def read_yaml_file(path: Path) -> dict[str, Any]:
    with open(path) as file:
        data = yaml.safe_load(file) or {}

        if not isinstance(data, dict):
            raise ValueError(
                f"YAML file {path} does not contain a dictionary at the top level.")

    return data
