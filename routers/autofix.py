from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import json
import re
import shutil

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config_loader import settings


router = APIRouter(
    prefix="/autofix",
    tags=["Auto Fix"],
)


SQL_TRAINING_FILE_PATH = Path("config/sql_agent_training.yaml")


class AutoFixSuggestion(BaseModel):
    question: str
    selected_agent: Optional[str]
    feedback: str
    comment: Optional[str]
    target_file: Optional[str]
    target_intent: Optional[str]
    can_apply: bool
    suggested_action: str
    reason: str


class AutoFixSuggestionsResponse(BaseModel):
    count: int
    suggestions: List[AutoFixSuggestion]


class ApplyAutoFixRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Failed user question that should be added to YAML training examples",
    )

    target_intent: str = Field(
        ...,
        description="Intent name inside config/sql_agent_training.yaml",
    )


class ApplyAutoFixResponse(BaseModel):
    status: str
    message: str
    target_file: str
    target_intent: str
    added_example: str
    backup_file: Optional[str]
    restart_required: bool


def normalize_text(value: str) -> str:
    """
    Normalize text for duplicate checking.
    """

    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", "", value)
    value = re.sub(r"\s+", " ", value)

    return value


def get_feedback_log_path() -> str:
    """
    Read feedback log path from YAML config.
    """

    return settings.get("logging", {}).get(
        "feedback_log_path",
        "logs/feedback_log.jsonl",
    )


def read_feedback_records() -> List[Dict]:
    """
    Read feedback JSONL file.
    """

    feedback_log_path = get_feedback_log_path()
    feedback_file = Path(feedback_log_path)

    if not feedback_file.exists():
        return []

    records = []

    try:
        with open(feedback_file, "r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    records.append(json.loads(line))

        return records

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read feedback log: {error}",
        )


def load_sql_training_yaml() -> Dict:
    """
    Load SQL Agent YAML training file.
    """

    if not SQL_TRAINING_FILE_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"SQL training file not found: {SQL_TRAINING_FILE_PATH}",
        )

    try:
        with open(SQL_TRAINING_FILE_PATH, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if data is None:
            data = {}

        return data

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read SQL training YAML: {error}",
        )


def save_sql_training_yaml(data: Dict) -> None:
    """
    Save updated SQL Agent YAML training file.
    """

    try:
        with open(SQL_TRAINING_FILE_PATH, "w", encoding="utf-8") as file:
            yaml.safe_dump(
                data,
                file,
                sort_keys=False,
                allow_unicode=True,
            )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save SQL training YAML: {error}",
        )


def create_training_backup() -> str:
    """
    Create backup before modifying YAML.
    """

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = Path(
        f"config/sql_agent_training_backup_{timestamp}.yaml"
    )

    shutil.copy(
        SQL_TRAINING_FILE_PATH,
        backup_path,
    )

    return str(backup_path)


def infer_sql_intent_from_question(question: str) -> Optional[str]:
    """
    Simple rule-based inference for failed prompts.

    This suggests where the failed question should be added.
    """

    question_lower = question.lower()

    if "department" in question_lower and (
        "count" in question_lower
        or "how many" in question_lower
        or "number" in question_lower
    ):
        return "department_employee_count"

    if "employee" in question_lower and (
        "total" in question_lower
        or "count" in question_lower
        or "how many" in question_lower
        or "number" in question_lower
    ):
        return "total_employees"

    if "overtime" in question_lower and (
        "highest" in question_lower
        or "top" in question_lower
        or "most" in question_lower
    ):
        return "highest_overtime"

    return None


def build_suggestion(record: Dict) -> AutoFixSuggestion:
    """
    Build one auto-fix suggestion from failed feedback.
    """

    question = record.get("question", "")
    selected_agent = record.get("selected_agent")
    feedback = record.get("feedback", "")
    comment = record.get("comment")

    target_intent = infer_sql_intent_from_question(question)

    if target_intent:
        return AutoFixSuggestion(
            question=question,
            selected_agent=selected_agent,
            feedback=feedback,
            comment=comment,
            target_file=str(SQL_TRAINING_FILE_PATH),
            target_intent=target_intent,
            can_apply=True,
            suggested_action=(
                f"Add this question as an example under "
                f"'{target_intent}' in config/sql_agent_training.yaml."
            ),
            reason=(
                "The question looks like a structured SQL/database question "
                "and can be improved by adding it to SQL Agent YAML training."
            ),
        )

    question_lower = question.lower()

    if any(
        keyword in question_lower
        for keyword in ["policy", "access", "privacy", "approval", "permission"]
    ):
        return AutoFixSuggestion(
            question=question,
            selected_agent=selected_agent,
            feedback=feedback,
            comment=comment,
            target_file=None,
            target_intent=None,
            can_apply=False,
            suggested_action=(
                "This looks like a RAG/policy question. Review orchestrator "
                "routing or improve HR policy document coverage."
            ),
            reason="This is not a SQL training fix.",
        )

    if any(
        keyword in question_lower
        for keyword in ["risk", "anomaly", "scorecard", "analytics"]
    ):
        return AutoFixSuggestion(
            question=question,
            selected_agent=selected_agent,
            feedback=feedback,
            comment=comment,
            target_file=None,
            target_intent=None,
            can_apply=False,
            suggested_action=(
                "This looks like an Analytics question. Review analytics routing "
                "or analytics agent logic."
            ),
            reason="This is not a SQL training fix.",
        )

    return AutoFixSuggestion(
        question=question,
        selected_agent=selected_agent,
        feedback=feedback,
        comment=comment,
        target_file=None,
        target_intent=None,
        can_apply=False,
        suggested_action=(
            "Review this prompt manually and decide whether it belongs to SQL, "
            "RAG, or Analytics."
        ),
        reason="No confident auto-fix intent was found.",
    )


@router.get(
    "/suggestions",
    response_model=AutoFixSuggestionsResponse,
)
def get_autofix_suggestions(
    limit: int = Query(default=20, ge=1, le=100),
) -> AutoFixSuggestionsResponse:
    """
    Read wrong/needs_improvement feedback and suggest safe fixes.
    """

    feedback_records = read_feedback_records()

    failed_records = [
        record
        for record in feedback_records
        if record.get("feedback") in ["wrong", "needs_improvement"]
    ]

    recent_failed_records = failed_records[-limit:]

    suggestions = [
        build_suggestion(record)
        for record in recent_failed_records
    ]

    return AutoFixSuggestionsResponse(
        count=len(suggestions),
        suggestions=suggestions,
    )


@router.post(
    "/apply",
    response_model=ApplyAutoFixResponse,
)
def apply_autofix(request: ApplyAutoFixRequest) -> ApplyAutoFixResponse:
    """
    Safely apply an auto-fix by adding a failed question
    to an existing SQL Agent YAML intent.

    This only updates examples.
    It does not change SQL queries.
    """

    training_data = load_sql_training_yaml()

    intents = training_data.get("intents", {})

    if request.target_intent not in intents:
        raise HTTPException(
            status_code=400,
            detail=f"Intent not found in YAML: {request.target_intent}",
        )

    intent_details = intents[request.target_intent]

    existing_examples = intent_details.get("examples", [])

    normalized_new_question = normalize_text(request.question)

    normalized_existing_examples = [
        normalize_text(example)
        for example in existing_examples
    ]

    if normalized_new_question in normalized_existing_examples:
        return ApplyAutoFixResponse(
            status="skipped",
            message="This question already exists in YAML examples.",
            target_file=str(SQL_TRAINING_FILE_PATH),
            target_intent=request.target_intent,
            added_example=request.question,
            backup_file=None,
            restart_required=False,
        )

    backup_file = create_training_backup()

    existing_examples.append(request.question)

    intent_details["examples"] = existing_examples
    intents[request.target_intent] = intent_details
    training_data["intents"] = intents

    save_sql_training_yaml(training_data)

    return ApplyAutoFixResponse(
        status="success",
        message=(
            "Auto-fix applied successfully. The question was added to YAML "
            "training examples. Restart FastAPI and run regression tests."
        ),
        target_file=str(SQL_TRAINING_FILE_PATH),
        target_intent=request.target_intent,
        added_example=request.question,
        backup_file=backup_file,
        restart_required=True,
    )