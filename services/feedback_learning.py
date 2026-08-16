from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path
from typing import Any

import json
import tempfile

import yaml


from services.context_rag_index import (
    build_context_rag_index,
)

from services.pattern_cache import (
    build_pattern_cache,
    normalize_text,
)


# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

CONTEXT_DIR = (
    PROJECT_ROOT
    / "context"
)

OVERRIDES_PATH = (
    CONTEXT_DIR
    / "feedback_overrides.yaml"
)

LOGS_DIR = (
    PROJECT_ROOT
    / "logs"
)

FEEDBACK_LOG_PATH = (
    LOGS_DIR
    / "feedback_log.jsonl"
)


# ---------------------------------------------------------
# TIME
# ---------------------------------------------------------

def current_utc_timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


# ---------------------------------------------------------
# JSONL AUDIT LOG
# ---------------------------------------------------------

def append_feedback_log(
    feedback_record: dict[str, Any],
) -> None:
    """
    Append one feedback event to the JSONL audit log.

    JSONL keeps one JSON object on every line.
    """

    LOGS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with FEEDBACK_LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as file:

        file.write(
            json.dumps(
                feedback_record,
                default=str,
            )
            + "\n"
        )


# ---------------------------------------------------------
# YAML LOADING
# ---------------------------------------------------------

def load_feedback_overrides() -> dict[
    str,
    Any,
]:
    """
    Load feedback_overrides.yaml.
    """

    if not OVERRIDES_PATH.exists():

        return {
            "version": 1,
            "description": (
                "Approved corrections learned "
                "from explicit user feedback."
            ),
            "overrides": [],
        }

    with OVERRIDES_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        feedback_data = yaml.safe_load(
            file
        )

    if feedback_data is None:

        return {
            "version": 1,
            "overrides": [],
        }

    return feedback_data


# ---------------------------------------------------------
# SAFE YAML WRITING
# ---------------------------------------------------------

def write_feedback_overrides(
    feedback_data: dict[str, Any],
) -> None:
    """
    Safely update feedback_overrides.yaml.

    A temporary file is written first. It then replaces
    the original file. This reduces the chance of leaving
    incomplete YAML if writing fails.
    """

    CONTEXT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = None

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".yaml",
            dir=CONTEXT_DIR,
            delete=False,
        ) as temporary_file:

            yaml.safe_dump(
                feedback_data,
                temporary_file,
                sort_keys=False,
                allow_unicode=True,
            )

            temporary_path = Path(
                temporary_file.name
            )

        temporary_path.replace(
            OVERRIDES_PATH
        )

    finally:

        if (
            temporary_path
            and temporary_path.exists()
        ):
            temporary_path.unlink(
                missing_ok=True
            )


# ---------------------------------------------------------
# YAML OVERRIDE UPSERT
# ---------------------------------------------------------

def upsert_feedback_override(
    feedback_record: dict[str, Any],
) -> dict[str, Any]:
    """
    Insert a new correction or update the existing
    correction for the same normalized question.
    """

    feedback_data = (
        load_feedback_overrides()
    )

    feedback_overrides = (
        feedback_data.setdefault(
            "overrides",
            [],
        )
    )

    normalized_question = (
        normalize_text(
            feedback_record["question"]
        )
    )

    expected_answer = (
        feedback_record.get(
            "expected_answer"
        )
    )

    # For this learning project, a correction becomes
    # approved when the user supplies an expected answer.
    #
    # In a production HR system, this should normally
    # require human review.
    if (
        isinstance(
            expected_answer,
            str,
        )
        and expected_answer.strip()
    ):
        learned_status = "approved"

    else:
        learned_status = "pending_review"

    learned_override = {

        "question": (
            feedback_record["question"]
        ),

        "normalized_question": (
            normalized_question
        ),

        "expected_answer": (
            expected_answer
        ),

        "correction": {
            "preferred_route": (
                feedback_record.get(
                    "selected_agent"
                )
            ),

            "comment": (
                feedback_record.get(
                    "comment"
                )
            ),
        },

        "status": learned_status,

        "created_at": (
            feedback_record["timestamp"]
        ),

        "updated_at": (
            feedback_record["timestamp"]
        ),
    }

    existing_index = None

    for index, existing_item in enumerate(
        feedback_overrides
    ):

        if (
            existing_item.get(
                "normalized_question"
            )
            == normalized_question
        ):

            existing_index = index
            break

    if existing_index is None:

        feedback_overrides.append(
            learned_override
        )

    else:

        original_created_at = (
            feedback_overrides[
                existing_index
            ].get(
                "created_at",
                feedback_record[
                    "timestamp"
                ],
            )
        )

        learned_override[
            "created_at"
        ] = original_created_at

        feedback_overrides[
            existing_index
        ] = learned_override

    write_feedback_overrides(
        feedback_data
    )

    return learned_override


# ---------------------------------------------------------
# MAIN FEEDBACK PROCESS
# ---------------------------------------------------------

def save_feedback(
    *,
    question: str,
    feedback: str,
    selected_agent: str | None,
    comment: str | None,
    expected_answer: str | None,
    original_response: dict[
        str,
        Any,
    ] | None,
) -> dict[str, Any]:
    """
    Save feedback and rebuild learning components
    when the answer was wrong.
    """

    feedback_record = {

        "question": question,

        "selected_agent": (
            selected_agent
        ),

        "feedback": feedback,

        "comment": comment,

        "expected_answer": (
            expected_answer
        ),

        "original_response": (
            original_response
        ),

        "timestamp": (
            current_utc_timestamp()
        ),
    }

    # Every feedback event is audited.
    append_feedback_log(
        feedback_record
    )

    learned_override = None
    cache_rebuilt = False
    context_documents_indexed = 0
    reindex_warning = None

    if feedback in {
        "wrong",
        "needs_improvement",
    }:

        learned_override = (
            upsert_feedback_override(
                feedback_record
            )
        )

        # Rebuild the fast lookup cache.
        build_pattern_cache()

        cache_rebuilt = True

        # Rebuild the YAML context collection.
        try:

            context_documents_indexed = (
                build_context_rag_index()
            )

        except Exception as error:

            # Feedback should remain saved even if
            # ChromaDB reindexing fails.
            reindex_warning = str(error)

    return {

        "feedback_record": (
            feedback_record
        ),

        "learned_override": (
            learned_override
        ),

        "cache_rebuilt": (
            cache_rebuilt
        ),

        "context_documents_indexed": (
            context_documents_indexed
        ),

        "reindex_warning": (
            reindex_warning
        ),
    }


# ---------------------------------------------------------
# RECENT FEEDBACK READER
# ---------------------------------------------------------

def get_recent_feedback(
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Read recent feedback events from JSONL.
    """

    if not FEEDBACK_LOG_PATH.exists():
        return []

    with FEEDBACK_LOG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        feedback_lines = (
            file.readlines()
        )

    recent_lines = (
        feedback_lines[-limit:]
    )

    return [
        json.loads(line)
        for line in recent_lines
        if line.strip()
    ]