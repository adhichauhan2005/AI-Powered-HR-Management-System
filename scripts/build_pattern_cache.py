from pathlib import Path

import sys


# ---------------------------------------------------------
# FIND PROJECT ROOT
# ---------------------------------------------------------

# Current file:
# hr_employee_portal/scripts/build_pattern_cache.py
#
# parents[0] = scripts
# parents[1] = hr_employee_portal
BACKEND_DIR = Path(
    __file__
).resolve().parents[1]


# Make project modules importable.
sys.path.insert(
    0,
    str(BACKEND_DIR),
)


# Import after adding the project root to Python path.
from services.pattern_cache import (
    CACHE_PATH,
    build_pattern_cache,
)


# ---------------------------------------------------------
# RUN CACHE BUILDER
# ---------------------------------------------------------

if __name__ == "__main__":

    # Your YAML files are stored in the separate
    # project-level context folder.
    glossary_path = (
        BACKEND_DIR
        / "context"
        / "hr_glossary.yaml"
    )

    print(
        "\nProject root:"
    )

    print(
        BACKEND_DIR
    )

    print(
        "\nExpected glossary location:"
    )

    print(
        glossary_path
    )

    print(
        "\nGlossary file exists:"
    )

    print(
        glossary_path.exists()
    )

    # Stop immediately with a clear message if
    # the glossary is in the wrong location.
    if not glossary_path.exists():

        raise FileNotFoundError(
            "\nhr_glossary.yaml was not found.\n"
            f"Place it here:\n{glossary_path}"
        )

    cache_data = build_pattern_cache()

    print(
        "\nPattern cache created successfully."
    )

    print(
        f"Cache location: {CACHE_PATH}"
    )

    print(
        "Total glossary aliases: "
        f"{len(cache_data['aliases'])}"
    )

    print(
        "Total canonical HR terms: "
        f"{len(cache_data['term_details'])}"
    )

    print(
        "Total approved feedback overrides: "
        f"{len(cache_data['overrides'])}"
    )