from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import (
    BaseModel,
    Field,
)


from routers.orchestrator import (
    orchestrator_graph,
)

from services.context_layer import (
    ContextResolution,
    resolve_question,
)

from services.priority_sql import (
    execute_priority_sql,
)

from services.response_formatter import (
    format_orchestrator_result,
)


# ---------------------------------------------------------
# FASTAPI ROUTER
# ---------------------------------------------------------

router = APIRouter(
    prefix="/hr-agent",
    tags=["Customer HR Agent"],
)


# ---------------------------------------------------------
# REQUEST MODEL
# ---------------------------------------------------------

class HRAgentRequest(BaseModel):
    """
    Request sent by the frontend.
    """

    question: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description=(
            "Natural-language HR question"
        ),
    )


# ---------------------------------------------------------
# RESPONSE MODEL
# ---------------------------------------------------------

class HRAgentResponse(BaseModel):
    """
    Clean customer-facing response.

    We return only the answer instead of exposing
    SQL, internal agent names or source dictionaries.
    """

    answer: str


# ---------------------------------------------------------
# APPROVED FEEDBACK OVERRIDE
# ---------------------------------------------------------

def get_override_answer(
    resolution: ContextResolution,
) -> str | None:
    """
    Return an approved corrected answer when the
    question matches feedback_overrides.yaml.
    """

    if not resolution.override:
        return None

    expected_answer = (
        resolution.override.get(
            "expected_answer"
        )
    )

    if (
        isinstance(
            expected_answer,
            str,
        )
        and expected_answer.strip()
    ):
        return expected_answer.strip()

    return None


# ---------------------------------------------------------
# NORMAL LANGGRAPH EXECUTION
# ---------------------------------------------------------

def run_normal_orchestrator(
    question: str,
) -> dict[str, Any]:
    """
    Send an unmatched question through the existing
    LangGraph orchestrator.
    """

    try:

        final_state = (
            orchestrator_graph.invoke(
                {
                    "question": question,
                }
            )
        )

        return final_state

    except HTTPException:
        # Keep an existing FastAPI error unchanged.
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "The HR Agent could not process "
                f"the question: {error}"
            ),
        ) from error


# ---------------------------------------------------------
# CUSTOMER HR AGENT ENDPOINT
# ---------------------------------------------------------

@router.post(
    "/ask",
    response_model=HRAgentResponse,
)
def ask_hr_agent(
    request: HRAgentRequest,
) -> HRAgentResponse:
    """
    Main customer-facing HR Agent flow.

    Processing priority:

    1. Approved feedback correction
    2. Deterministic priority SQL
    3. Existing LangGraph orchestrator
    4. Clean response formatting
    """

    question = request.question.strip()

    # -----------------------------------------------------
    # STEP 1: RESOLVE QUESTION CONTEXT
    # -----------------------------------------------------

    resolution = resolve_question(
        question
    )

    # -----------------------------------------------------
    # STEP 2: CHECK APPROVED FEEDBACK
    # -----------------------------------------------------

    override_answer = (
        get_override_answer(
            resolution
        )
    )

    if override_answer:

        return HRAgentResponse(
            answer=override_answer
        )

    # -----------------------------------------------------
    # STEP 3: RUN PRIORITY SQL
    # -----------------------------------------------------

    if (
        resolution.route
        == "priority_sql"
    ):

        try:

            priority_result = (
                execute_priority_sql(
                    resolution
                )
            )

        except Exception as error:

            raise HTTPException(
                status_code=500,
                detail=(
                    "The priority HR database "
                    f"query failed: {error}"
                ),
            ) from error

        return HRAgentResponse(
            answer=priority_result[
                "answer"
            ]
        )

    # -----------------------------------------------------
    # STEP 4: NORMAL LANGGRAPH ROUTING
    # -----------------------------------------------------

    orchestrator_result = (
        run_normal_orchestrator(
            question
        )
    )

    # -----------------------------------------------------
    # STEP 5: CUSTOMER-FRIENDLY RESPONSE
    # -----------------------------------------------------

    formatted_answer = (
        format_orchestrator_result(
            orchestrator_result
        )
    )

    return HRAgentResponse(
        answer=formatted_answer
    )