from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from pathlib import Path
from typing import Any

import re

import yaml

from services.pattern_cache import (
    load_pattern_cache,
    normalize_text,
)


# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

CONTEXT_DIR = (
    BACKEND_DIR
    / "context"
)


# ---------------------------------------------------------
# CONTEXT RESULT MODEL
# ---------------------------------------------------------

@dataclass
class ContextResolution:
    """
    Structured result produced by the context layer.

    The orchestrator will later use this result to decide
    whether the question should:

    - use an approved correction,
    - use deterministic SQL,
    - or continue through normal LangGraph routing.
    """

    original_question: str

    normalized_question: str

    concepts: list[str] = field(
        default_factory=list
    )

    route: str | None = None

    action: str | None = None

    parameters: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    override: dict[
        str,
        Any,
    ] | None = None

    reason: str = (
        "No priority context rule matched."
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert the dataclass into a normal dictionary.
        """

        return asdict(self)


# ---------------------------------------------------------
# YAML LOADING
# ---------------------------------------------------------

def load_context_yaml(
    filename: str,
) -> dict[str, Any]:
    """
    Load one YAML file from backend/config/context.
    """

    file_path = (
        CONTEXT_DIR
        / filename
    )

    if not file_path.exists():
        return {}

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        yaml_data = yaml.safe_load(
            file
        )

    if yaml_data is None:
        return {}

    return yaml_data


# ---------------------------------------------------------
# PHRASE MATCHING
# ---------------------------------------------------------

def contains_phrase(
    normalized_question: str,
    phrase: str,
) -> bool:
    """
    Check whether a complete word or phrase appears
    in the normalized question.

    This prevents incorrect partial matches.

    Example:

    "pay" should match:
    "show employee pay"

    But it should not accidentally match a random
    section of a larger word.
    """

    normalized_phrase = normalize_text(
        phrase
    )

    if not normalized_phrase:
        return False

    phrase_pattern = (
        rf"(?:^|\s)"
        rf"{re.escape(normalized_phrase)}"
        rf"(?:$|\s)"
    )

    return (
        re.search(
            phrase_pattern,
            normalized_question,
        )
        is not None
    )


# ---------------------------------------------------------
# GLOSSARY CONCEPT DETECTION
# ---------------------------------------------------------

def detect_concepts(
    question: str,
) -> list[str]:
    """
    Detect canonical HR concepts in a question.

    Example:

    "Show emp count by dept"

    becomes:

    [
        "employee",
        "department"
    ]
    """

    normalized_question = normalize_text(
        question
    )

    cache_data = load_pattern_cache()

    detected_concepts: list[str] = []

    alias_items = list(
        cache_data.get(
            "aliases",
            {},
        ).items()
    )

    # Check longer aliases first.
    #
    # For example:
    # "job title" should be checked before "title".
    alias_items.sort(
        key=lambda item: len(
            item[0]
        ),
        reverse=True,
    )

    for (
        alias,
        canonical_name,
    ) in alias_items:

        if contains_phrase(
            normalized_question,
            alias,
        ):

            if (
                canonical_name
                not in detected_concepts
            ):
                detected_concepts.append(
                    canonical_name
                )

    return detected_concepts


# ---------------------------------------------------------
# JOB TITLE EXTRACTION
# ---------------------------------------------------------

def singularize_job_title(
    title: str,
) -> str:
    """
    Convert a simple plural job title into singular form.

    Examples:

    "AI Engineers"
    becomes:
    "AI Engineer"

    "Data Analysts"
    becomes:
    "Data Analyst"
    """

    title_words = title.split()

    if (
        title_words
        and title_words[-1].endswith("s")
        and len(title_words[-1]) > 3
    ):
        title_words[-1] = (
            title_words[-1][:-1]
        )

    return " ".join(
        title_words
    )


def format_job_title(
    title: str,
) -> str:
    """
    Format job-title words while preserving common
    technical acronyms.

    Examples:

    "ai engineer"
    becomes:
    "AI Engineer"

    "sql developer"
    becomes:
    "SQL Developer"
    """

    acronyms = {
        "ai",
        "bi",
        "hr",
        "it",
        "ml",
        "qa",
        "sql",
    }

    formatted_words = []

    for word in title.split():

        if word.casefold() in acronyms:
            formatted_words.append(
                word.upper()
            )

        else:
            formatted_words.append(
                word.capitalize()
            )

    return " ".join(
        formatted_words
    )


def extract_job_title(
    question: str,
) -> str | None:
    """
    Extract a designation from a salary question.

    Supported examples:

    "AI engineer salary"

    "salary of data analysts"

    "salary for software engineers"
    """

    normalized_question = normalize_text(
        question
    )

    job_title_patterns = [

        # Example:
        # salary of AI engineers
        # salary for data analysts
        (
            r"(?:salary|pay|compensation|earnings)"
            r"\s+(?:of|for)"
            r"\s+(?:an?\s+|the\s+)?"
            r"(?P<title>.+)$"
        ),

        # Example:
        # AI engineer salary
        # software developer pay
        (
            r"^(?P<title>.+?)"
            r"\s+"
            r"(?:salary|pay|compensation|earnings)$"
        ),
    ]

    job_title_candidate = None

    for pattern in job_title_patterns:

        match = re.search(
            pattern,
            normalized_question,
        )

        if match:

            job_title_candidate = (
                match.group("title").strip()
            )

            break

    if not job_title_candidate:
        return None

    removable_prefixes = [
        "what is the",
        "what is",
        "show me the",
        "show me",
        "tell me the",
        "tell me",
        "find the",
        "find",
        "current",
    ]

    prefix_removed = True

    while prefix_removed:

        prefix_removed = False

        for prefix in removable_prefixes:

            if job_title_candidate.startswith(
                prefix + " "
            ):

                job_title_candidate = (
                    job_title_candidate[
                        len(prefix):
                    ].strip()
                )

                prefix_removed = True

    # These words describe general salary questions.
    # They are not job titles.
    invalid_job_titles = {
        "employee",
        "employees",
        "staff",
        "worker",
        "workers",
        "department",
        "departments",
        "lowest",
        "highest",
        "minimum",
        "maximum",
        "average",
        "current",
    }

    if (
        not job_title_candidate
        or job_title_candidate
        in invalid_job_titles
    ):
        return None

    job_title_candidate = (
        singularize_job_title(
            job_title_candidate
        )
    )

    return format_job_title(
        job_title_candidate
    )


# ---------------------------------------------------------
# SUPERLATIVE DETECTION
# ---------------------------------------------------------

def find_superlative(
    normalized_question: str,
    query_rules: dict[str, Any],
) -> tuple[
    str | None,
    dict[str, Any],
]:
    """
    Detect words such as lowest and highest.
    """

    superlative_rules = (
        query_rules.get(
            "superlatives",
            {},
        )
    )

    for (
        superlative_name,
        superlative_details,
    ) in superlative_rules.items():

        aliases = (
            superlative_details.get(
                "aliases",
                [],
            )
        )

        for alias in aliases:

            if contains_phrase(
                normalized_question,
                alias,
            ):

                return (
                    superlative_name,
                    superlative_details,
                )

    return None, {}


# ---------------------------------------------------------
# MAIN CONTEXT RESOLVER
# ---------------------------------------------------------

def resolve_question(
    question: str,
) -> ContextResolution:
    """
    Resolve a user question before LangGraph routing.

    Priority:

    1. Approved feedback correction
    2. Deterministic salary rule
    3. Designation extraction
    4. Normal orchestrator
    """

    normalized_question = normalize_text(
        question
    )

    detected_concepts = detect_concepts(
        question
    )

    cache_data = load_pattern_cache()

    # -----------------------------------------------------
    # PRIORITY 1: APPROVED FEEDBACK
    # -----------------------------------------------------

    approved_override = (
        cache_data.get(
            "overrides",
            {},
        ).get(
            normalized_question
        )
    )

    if approved_override:

        return ContextResolution(

            original_question=question,

            normalized_question=(
                normalized_question
            ),

            concepts=detected_concepts,

            route="override",

            action=(
                "approved_feedback_override"
            ),

            parameters=(
                approved_override.get(
                    "correction",
                    {},
                )
            ),

            override=approved_override,

            reason=(
                "An approved feedback correction "
                "matched this question."
            ),
        )

    # -----------------------------------------------------
    # LOAD QUERY RULES
    # -----------------------------------------------------

    query_rules = load_context_yaml(
        "query_rules.yaml"
    )

    (
        superlative_name,
        superlative_details,
    ) = find_superlative(
        normalized_question=(
            normalized_question
        ),
        query_rules=query_rules,
    )

    # -----------------------------------------------------
    # PRIORITY 2: LOWEST OR HIGHEST SALARY
    # -----------------------------------------------------

    if (
        "salary" in detected_concepts
        and superlative_name
        in {
            "lowest",
            "highest",
        }
    ):

        direction = (
            superlative_details.get(
                "direction",
                "ASC",
            )
        )

        return ContextResolution(

            original_question=question,

            normalized_question=(
                normalized_question
            ),

            concepts=detected_concepts,

            route="priority_sql",

            action="salary_superlative",

            parameters={
                "direction": direction,

                # Always one result.
                "result_limit": 1,

                # Compare only the latest payroll
                # record for every employee.
                "use_latest_payroll": True,
            },

            reason=(
                f"The question asks for the "
                f"{superlative_name} current salary, "
                f"so exactly one employee must be "
                f"returned."
            ),
        )

    # -----------------------------------------------------
    # PRIORITY 3: SALARY BY DESIGNATION
    # -----------------------------------------------------

    if "salary" in detected_concepts:

        job_title = extract_job_title(
            question
        )

        if job_title:

            updated_concepts = list(
                detected_concepts
            )

            if (
                "designation"
                not in updated_concepts
            ):
                updated_concepts.append(
                    "designation"
                )

            return ContextResolution(

                original_question=question,

                normalized_question=(
                    normalized_question
                ),

                concepts=updated_concepts,

                route="priority_sql",

                action=(
                    "salary_by_job_title"
                ),

                parameters={
                    "job_title": job_title,
                    "use_latest_payroll": True,
                },

                reason=(
                    f"'{job_title}' was resolved "
                    f"as an employee designation. "
                    f"Salary was resolved as "
                    f"Payroll.basic_salary."
                ),
            )

    # -----------------------------------------------------
    # NORMAL ORCHESTRATOR
    # -----------------------------------------------------

    return ContextResolution(

        original_question=question,

        normalized_question=(
            normalized_question
        ),

        concepts=detected_concepts,

        route=None,

        action=None,

        parameters={},

        override=None,

        reason=(
            "No priority context rule matched. "
            "Continue through the normal "
            "LangGraph orchestrator."
        ),
    )