from pathlib import Path
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"


def load_query_config(filename: str) -> dict[str, Any]:
    """
    Load SQL queries from a YAML file inside the config folder.
    """

    file_path = CONFIG_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"SQL query configuration file not found: {file_path}"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

    except yaml.YAMLError as error:
        raise ValueError(
            f"Invalid YAML inside {filename}: {error}"
        ) from error

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(
            f"The top level of {filename} must be a dictionary."
        )

    return data