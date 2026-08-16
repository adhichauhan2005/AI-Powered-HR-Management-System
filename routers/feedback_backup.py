from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config_loader import settings


router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"],
)


class FeedbackRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Original user question asked to the system",
    )

    selected_agent: Optional[str] = Field(
        default=None,
        description="Agent that answered the question: sql, rag, analytics, or orchestrator",
    )

    feedback: Literal["correct", "wrong", "needs_improvement"] = Field(
        ...,
        description="User feedback for the generated answer",
    )

    comment: Optional[str] = Field(
        default=None,
        description="Optional user comment explaining the feedback",
    )

    expected_answer: Optional[str] = Field(
        default=None,
        description="Optional expected answer if the response was wrong",
    )

    original_response: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional original system response",
    )


class FeedbackResponse(BaseModel):
    status: str
    message: str
    saved_to: str
    feedback_record: Dict[str, Any]


class RecentFeedbackResponse(BaseModel):
    count: int
    feedback_records: List[Dict[str, Any]]


def get_current_utc_timestamp() -> str:
    """
    Return current UTC timestamp.
    This helps us know exactly when feedback was submitted.
    """

    return datetime.now(timezone.utc).isoformat()


def get_feedback_log_path() -> str:
    """
    Read feedback log path from YAML config.
    If YAML value is missing, use default path.
    """

    return settings.get("logging", {}).get(
        "feedback_log_path",
        "logs/feedback_log.jsonl",
    )


def write_feedback_log(feedback_record: Dict[str, Any]) -> str:
    """
    Save one feedback record into a JSON Lines file.

    JSONL means:
    - each line is one JSON object
    - easy to append
    - easy to read later for prompt discovery
    """

    log_path = get_feedback_log_path()
    log_file = Path(log_path)

    try:
        log_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(log_file, "a", encoding="utf-8") as file:
            file.write(json.dumps(feedback_record, default=str) + "\n")

        return log_path

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save feedback log: {error}",
        )


@router.post(
    "",
    response_model=FeedbackResponse,
)
def submit_feedback(feedback_request: FeedbackRequest) -> FeedbackResponse:
    """
    Save user feedback for any agent response.

    This endpoint can be called by:
    - Swagger
    - frontend UI
    - future feedback buttons
    """

    feedback_record = {
        "question": feedback_request.question,
        "selected_agent": feedback_request.selected_agent,
        "feedback": feedback_request.feedback,
        "comment": feedback_request.comment,
        "expected_answer": feedback_request.expected_answer,
        "original_response": feedback_request.original_response,
        "timestamp": get_current_utc_timestamp(),
    }

    saved_path = write_feedback_log(feedback_record)

    return FeedbackResponse(
        status="success",
        message="Feedback saved successfully.",
        saved_to=saved_path,
        feedback_record=feedback_record,
    )


@router.get(
    "/recent",
    response_model=RecentFeedbackResponse,
)
def get_recent_feedback(
    limit: int = Query(default=10, ge=1, le=100),
) -> RecentFeedbackResponse:
    """
    Read recent feedback records.

    This is useful for:
    - debugging
    - prompt discovery
    - checking wrong answers
    """

    log_path = get_feedback_log_path()
    log_file = Path(log_path)

    if not log_file.exists():
        return RecentFeedbackResponse(
            count=0,
            feedback_records=[],
        )

    try:
        with open(log_file, "r", encoding="utf-8") as file:
            lines = file.readlines()

        recent_lines = lines[-limit:]

        feedback_records = [
            json.loads(line)
            for line in recent_lines
            if line.strip()
        ]

        return RecentFeedbackResponse(
            count=len(feedback_records),
            feedback_records=feedback_records,
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read feedback log: {error}",
        )