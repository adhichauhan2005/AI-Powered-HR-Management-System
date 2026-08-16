from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pickle
import re

import yaml


# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

# pattern_cache.py is inside:
# backend/services/pattern_cache.py
#
# parents[0] = services
# parents[1] = backend
BACKEND_DIR = Path(__file__).resolve().parents[1]

CONTEXT_DIR = (
    BACKEND_DIR
    / "context"
)

CACHE_DIR = (
    BACKEND_DIR
    / "cache"
)

CACHE_PATH = (
    CACHE_DIR
    / "query_patterns.pkl"
)


# ---------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------

def normalize_text(value: str) -> str:
    """
    Convert natural-language text into a stable lookup key.

    Examples:

    "Who Has the Lowest Salary?"
    becomes:
    "who has the lowest salary"

    "EMP-001!"
    becomes:
    "emp 001"
    """

    normalized_value = value.casefold().strip()

    # Replace punctuation and special characters with spaces.
    normalized_value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized_value,
    )

    # Replace repeated spaces with one space.
    normalized_value = re.sub(
        r"\s+",
        " ",
        normalized_value,
    )

    return normalized_value.strip()


# ---------------------------------------------------------
# YAML LOADER
# ---------------------------------------------------------

def load_yaml_file(
    file_path: Path,
    required: bool = False,
) -> dict[str, Any]:
    """
    Safely read one YAML file.

    If a required file is missing, show its exact
    expected location instead of silently returning
    an empty dictionary.
    """

    if not file_path.exists():

        if required:
            raise FileNotFoundError(
                "\nRequired YAML file was not found.\n"
                f"Expected location:\n{file_path}\n"
                "\nMake sure the file is inside:\n"
                "config/context/"
            )

        return {}

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        yaml_data = yaml.safe_load(file)

    if yaml_data is None:
        return {}

    if not isinstance(yaml_data, dict):
        raise ValueError(
            f"Invalid YAML structure in: {file_path}"
        )

    return yaml_data


# ---------------------------------------------------------
# CACHE BUILDING
# ---------------------------------------------------------

def build_pattern_cache() -> dict[str, Any]:
    """
    Build the query-pattern cache from YAML files.

    Source files:

    1. hr_glossary.yaml
       Contains employee, department, salary and other
       HR terms and aliases.

    2. feedback_overrides.yaml
       Contains approved corrections learned from
       user feedback.

    YAML remains the source of truth.

    The .pkl file is only a generated fast-lookup cache.
    """

    glossary_path = (
        CONTEXT_DIR
        / "hr_glossary.yaml"
    )

    feedback_overrides_path = (
        CONTEXT_DIR
        / "feedback_overrides.yaml"
    )

    glossary_data = load_yaml_file(
    glossary_path,
    required=True,
    ) 

    feedback_data = load_yaml_file(
        feedback_overrides_path
    )

    # Maps each alias to its canonical HR term.
    #
    # Example:
    # "emp" -> "employee"
    # "staff member" -> "employee"
    # "dept" -> "department"
    aliases: dict[str, str] = {}

    # Stores the complete information for each
    # canonical term.
    term_details: dict[
        str,
        dict[str, Any],
    ] = {}

    glossary_terms = glossary_data.get(
        "terms",
        {},
    )

    for (
        canonical_name,
        details,
    ) in glossary_terms.items():

        term_details[canonical_name] = details

        term_aliases = set(
            details.get(
                "aliases",
                [],
            )
        )

        # The canonical name should also work as an alias.
        #
        # Example:
        # employee -> employee
        term_aliases.add(
            canonical_name
        )

        for alias in term_aliases:

            normalized_alias = normalize_text(
                str(alias)
            )

            if normalized_alias:
                aliases[
                    normalized_alias
                ] = canonical_name

    # Approved feedback corrections are stored using
    # normalized questions as keys.
    approved_overrides: dict[
        str,
        dict[str, Any],
    ] = {}

    feedback_overrides = feedback_data.get(
        "overrides",
        [],
    )

    for feedback_item in feedback_overrides:

        # Only approved feedback should immediately
        # change system behavior.
        if (
            feedback_item.get("status")
            != "approved"
        ):
            continue

        question = (
            feedback_item.get(
                "normalized_question"
            )
            or feedback_item.get(
                "question",
                "",
            )
        )

        normalized_question = normalize_text(
            str(question)
        )

        if normalized_question:
            approved_overrides[
                normalized_question
            ] = feedback_item

    cache_data = {
        "version": 1,

        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "aliases": aliases,

        "term_details": term_details,

        "overrides": approved_overrides,
    }

    # Create the cache directory if it does not exist.
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save the locally generated Python object.
    with CACHE_PATH.open(
        "wb",
    ) as file:
        pickle.dump(
            cache_data,
            file,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    return cache_data


# ---------------------------------------------------------
# CACHE STALENESS CHECK
# ---------------------------------------------------------

def is_cache_stale() -> bool:
    """
    Return True when a YAML context file is newer than
    query_patterns.pkl.

    This makes sure changes to YAML are not ignored.
    """

    if not CACHE_PATH.exists():
        return True

    cache_modified_time = (
        CACHE_PATH.stat().st_mtime
    )

    yaml_files = list(
        CONTEXT_DIR.glob("*.yaml")
    )

    for yaml_file in yaml_files:

        if (
            yaml_file.stat().st_mtime
            > cache_modified_time
        ):
            return True

    return False


# ---------------------------------------------------------
# CACHE LOADING
# ---------------------------------------------------------

def load_pattern_cache(
    rebuild: bool = False,
) -> dict[str, Any]:
    """
    Load the generated pattern cache.

    Rebuild the cache when:

    - rebuild=True
    - the cache does not exist
    - a YAML file is newer than the cache
    - the cache cannot be read
    """

    if (
        rebuild
        or is_cache_stale()
    ):
        return build_pattern_cache()

    try:

        with CACHE_PATH.open(
            "rb",
        ) as file:
            cache_data = pickle.load(
                file
            )

        if not isinstance(
            cache_data,
            dict,
        ):
            return build_pattern_cache()

        return cache_data

    except (
        pickle.PickleError,
        EOFError,
        AttributeError,
        ValueError,
    ):

        return build_pattern_cache()