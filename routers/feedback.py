from __future__ import annotations

from typing import (
    Any,
    Literal,
)

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from pydantic import (
    BaseModel,
    Field,
)


from services.feedback_learning import (
    get_recent_feedback,
    save_feedback,
)


# ---------------------------------------------------------
# FASTAPI ROUTER
# ---------------------------------------------------------

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback Learning"],
)


# ---------------------------------------------------------
# REQUEST MODEL
# ---------------------------------------------------------

class FeedbackRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=2,
        max_length=1000,
    )

    selected_agent: str | None = None

    feedback: Literal[
        "correct",
        "wrong",
        "needs_improvement",
    ]

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )

    expected_answer: str | None = Field(
        default=None,
        max_length=5000,
    )

    original_response: dict[
        str,
        Any,
    ] | None = None


# ---------------------------------------------------------
# RESPONSE MODEL
# ---------------------------------------------------------

class FeedbackResponse(BaseModel):

    status: str

    message: str

    learned_status: str | None = None

    cache_rebuilt: bool

    context_documents_indexed: int

    reindex_warning: str | None = None


# ---------------------------------------------------------
# SUBMIT FEEDBACK
# ---------------------------------------------------------

@router.post(
    "",
    response_model=FeedbackResponse,
)
def submit_feedback(
    request: FeedbackRequest,
) -> FeedbackResponse:
    """
    Save feedback and learn from corrections.
    """

    if request.feedback in {
        "wrong",
        "needs_improvement",
    }:

        if (
            not request.comment
            and not request.expected_answer
        ):

            raise HTTPException(
                status_code=422,
                detail=(
                    "Wrong feedback requires "
                    "a comment or expected answer."
                ),
            )

    result = save_feedback(

        question=request.question,

        feedback=request.feedback,

        selected_agent=(
            request.selected_agent
        ),

        comment=request.comment,

        expected_answer=(
            request.expected_answer
        ),

        original_response=(
            request.original_response
        ),
    )

    learned_override = result.get(
        "learned_override"
    )

    if learned_override:

        learned_status = (
            learned_override.get(
                "status"
            )
        )

    else:
        learned_status = None

    if request.feedback == "correct":

        message = (
            "Feedback submitted. Thank you."
        )

    elif learned_status == "approved":

        message = (
            "Correction saved and activated "
            "in the context layer."
        )

    else:

        message = (
            "Correction saved for review."
        )

    return FeedbackResponse(

        status="success",

        message=message,

        learned_status=(
            learned_status
        ),

        cache_rebuilt=(
            result["cache_rebuilt"]
        ),

        context_documents_indexed=(
            result[
                "context_documents_indexed"
            ]
        ),

        reindex_warning=(
            result["reindex_warning"]
        ),
    )


# ---------------------------------------------------------
# RECENT FEEDBACK
# ---------------------------------------------------------

@router.get(
    "/recent",
)
def read_recent_feedback(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
) -> dict[str, Any]:
    """
    Return recent feedback for debugging.
    """

    feedback_records = (
        get_recent_feedback(
            limit=limit
        )
    )

    return {
        "count": len(
            feedback_records
        ),

        "feedback_records": (
            feedback_records
        ),
    }