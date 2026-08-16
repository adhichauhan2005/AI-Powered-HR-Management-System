from pathlib import Path
from typing import Dict, List, Optional
import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config_loader import settings


router = APIRouter(
    prefix="/prompt-discovery",
    tags=["Prompt Discovery"],
)


class PromptDiscoveryItem(BaseModel):
    question: str
    selected_agent: Optional[str]
    feedback: str
    comment: Optional[str]
    expected_answer: Optional[str]
    suggested_action: str


class PromptDiscoveryResponse(BaseModel):
    count: int
    items: List[PromptDiscoveryItem]


def get_feedback_log_path() -> str:
    """
    Get feedback log path from YAML config.
    """

    return settings.get("logging", {}).get(
        "feedback_log_path",
        "logs/feedback_log.jsonl",
    )


def read_feedback_records() -> List[Dict]:
    """
    Read all feedback records from feedback JSONL file.
    """

    feedback_log_path = get_feedback_log_path()
    feedback_file = Path(feedback_log_path)

    if not feedback_file.exists():
        return []

    try:
        records = []

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


def suggest_action(question: str, selected_agent: Optional[str]) -> str:
    """
    Suggest what to do with a failed prompt.

    This is a simple prompt discovery rule system.
    """

    question_lower = question.lower()

    if "employee" in question_lower and (
        "total" in question_lower
        or "count" in question_lower
        or "how many" in question_lower
    ):
        return "Add this prompt under total_employees intent in config/sql_agent_training.yaml."

    if "department" in question_lower and (
        "count" in question_lower
        or "how many" in question_lower
    ):
        return "Add this prompt under department_employee_count intent in config/sql_agent_training.yaml."

    if (
        "policy" in question_lower
        or "access" in question_lower
        or "privacy" in question_lower
        or "approval" in question_lower
    ):
        return "This looks like a RAG question. Improve orchestrator routing or add policy examples."

    if (
        "risk" in question_lower
        or "anomaly" in question_lower
        or "scorecard" in question_lower
    ):
        return "This looks like an Analytics question. Improve orchestrator analytics routing."

    return "Review this prompt manually and decide whether it belongs to SQL, RAG, or Analytics."


@router.get(
    "/failed-prompts",
    response_model=PromptDiscoveryResponse,
)
def get_failed_prompts(
    limit: int = Query(default=20, ge=1, le=100),
) -> PromptDiscoveryResponse:
    """
    Show wrong or needs_improvement feedback prompts.

    This helps us discover prompts that need YAML training updates.
    """

    feedback_records = read_feedback_records()

    failed_records = [
        record
        for record in feedback_records
        if record.get("feedback") in ["wrong", "needs_improvement"]
    ]

    recent_failed_records = failed_records[-limit:]

    items = []

    for record in recent_failed_records:
        question = record.get("question", "")
        selected_agent = record.get("selected_agent")

        items.append(
            PromptDiscoveryItem(
                question=question,
                selected_agent=selected_agent,
                feedback=record.get("feedback", ""),
                comment=record.get("comment"),
                expected_answer=record.get("expected_answer"),
                suggested_action=suggest_action(question, selected_agent),
            )
        )

    return PromptDiscoveryResponse(
        count=len(items),
        items=items,
    )