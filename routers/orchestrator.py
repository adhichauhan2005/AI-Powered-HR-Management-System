from typing import Any, Literal, TypedDict

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine

from routers.rag_agent import (
    build_llama_prompt,
    call_ollama as call_rag_llama,
    retrieve_policy_chunks,
)

from routers.sql_agent import (
    QUERY_TEMPLATES,
    detect_intent,
    validate_select_query,
)

from routers.analytics_agent import (
    get_attendance_risk,
    get_payroll_anomalies,
    get_department_scorecard,
)


# ---------------------------------------------------------
# FASTAPI ROUTER
# ---------------------------------------------------------
router = APIRouter(
    prefix="/orchestrator",
    tags=["LangGraph Orchestrator"],
)


# ---------------------------------------------------------
# API REQUEST MODEL
# ---------------------------------------------------------
class OrchestratorRequest(BaseModel):
    question: str


# ---------------------------------------------------------
# API RESPONSE MODEL
# ---------------------------------------------------------
class OrchestratorResponse(BaseModel):
    question: str
    selected_agent: str
    route_reason: str
    answer_type: str

    generated_sql: str | None = None
    row_count: int | None = None
    results: list[dict[str, Any]] | None = None

    answer: str | None = None
    sources: list[dict[str, Any]] | None = None

    analysis_name: str | None = None


# ---------------------------------------------------------
# LANGGRAPH SHARED STATE
# ---------------------------------------------------------
class OrchestratorState(TypedDict, total=False):
    question: str

    selected_agent: Literal["sql", "rag", "analytics"]
    route_reason: str
    answer_type: str

    generated_sql: str
    row_count: int
    results: list[dict[str, Any]]

    answer: str
    sources: list[dict[str, Any]]

    analysis_name: str


# ---------------------------------------------------------
# NODE 1: ROUTE QUESTION
# ---------------------------------------------------------
def route_question_node(
    state: OrchestratorState,
) -> OrchestratorState:
    """
    Decide whether the user question should go to:
    - SQL Agent
    - RAG Agent
    - Analytics Agent
    """

    question = state["question"]
    question_lower = question.lower()

    # -----------------------------------------------------
    # STEP 1: Analytics questions
    # -----------------------------------------------------
    # These should be checked first because words like
    # "attendance" and "payroll" may also appear in SQL questions.
    analytics_keywords = [
        "risk",
        "risky",
        "anomaly",
        "anomalies",
        "unusual",
        "outlier",
        "outliers",
        "pattern",
        "patterns",
        "scorecard",
        "analytics",
        "analysis",
        "predict",
        "prediction",
        "detect",
        "identify risky",
        "attendance risk",
        "payroll anomalies",
        "department scorecard",
    ]

    if any(keyword in question_lower for keyword in analytics_keywords):
        return {
            "selected_agent": "analytics",
            "route_reason": (
                "The question asks for risk, anomaly, scorecard, "
                "or analytical pattern detection, so it should be "
                "handled by the Analytics Agent."
            ),
            "answer_type": "analytics_answer",
        }

    # -----------------------------------------------------
    # STEP 2: Policy/privacy/access questions
    # -----------------------------------------------------
    access_policy_keywords = [
        "who can access",
        "access payroll",
        "access salary",
        "access employee information",
        "access personal information",
        "authorized",
        "permission",
        "permissions",
        "confidential",
        "privacy",
        "data privacy",
        "sensitive",
        "allowed to access",
    ]

    if any(keyword in question_lower for keyword in access_policy_keywords):
        return {
            "selected_agent": "rag",
            "route_reason": (
                "The question is about access, privacy, authorization, "
                "or HR policy, so it should be answered from policy documents."
            ),
            "answer_type": "policy_document_answer",
        }

    # -----------------------------------------------------
    # STEP 3: General RAG policy/document questions
    # -----------------------------------------------------
    rag_keywords = [
        "policy",
        "rule",
        "rules",
        "eligible",
        "eligibility",
        "approval",
        "approve",
        "reject",
        "allowed",
        "handbook",
        "guideline",
        "guidelines",
        "what happens if",
        "what should",
        "can employee",
    ]

    if any(keyword in question_lower for keyword in rag_keywords):
        return {
            "selected_agent": "rag",
            "route_reason": (
                "The question looks like an HR policy or "
                "document-based question."
            ),
            "answer_type": "policy_document_answer",
        }

    # -----------------------------------------------------
    # STEP 4: Structured SQL questions
    # -----------------------------------------------------
    sql_keywords = [
        "employee count",
        "count",
        "how many",
        "highest",
        "lowest",
        "average",
        "salary",
        "payroll",
        "overtime",
        "absent",
        "attendance",
        "department",
        "performance",
        "rating",
        "certification status",
        "training completion",
        "top",
        "summary",
    ]

    if any(keyword in question_lower for keyword in sql_keywords):
        return {
            "selected_agent": "sql",
            "route_reason": (
                "The question looks like a structured-data "
                "question that should be answered from MySQL."
            ),
            "answer_type": "structured_database_answer",
        }

    # Default route:
    # General unclear HR questions go to RAG because it is safer
    # for explanation-based answers.
    return {
        "selected_agent": "rag",
        "route_reason": (
            "The question was not clearly analytical or structured, "
            "so it was routed to the HR policy RAG Agent."
        ),
        "answer_type": "policy_document_answer",
    }


# ---------------------------------------------------------
# CONDITIONAL EDGE FUNCTION
# ---------------------------------------------------------
def choose_next_agent(
    state: OrchestratorState,
) -> Literal["sql_agent", "rag_agent", "analytics_agent"]:
    """
    LangGraph uses this function after route_question_node.

    It checks selected_agent and decides which node should run next.
    """

    if state["selected_agent"] == "sql":
        return "sql_agent"

    if state["selected_agent"] == "analytics":
        return "analytics_agent"

    return "rag_agent"


# ---------------------------------------------------------
# NODE 2: SQL AGENT
# ---------------------------------------------------------
def sql_agent_node(
    state: OrchestratorState,
) -> OrchestratorState:
    """
    Execute the existing rule-based SQL Agent.
    """

    question = state["question"]

    try:
        intent = detect_intent(question)

    except HTTPException as error:
        return {
            "selected_agent": "sql",
            "route_reason": (
                "The orchestrator routed the question to SQL, "
                "but SQL Agent V1 could not match a safe query template."
            ),
            "answer_type": "sql_agent_no_match",
            "answer": str(error.detail),
            "results": [],
            "row_count": 0,
        }

    template = QUERY_TEMPLATES[intent]
    sql_query = template["sql"].strip()

    validate_select_query(sql_query)

    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))

            rows = [
                dict(row)
                for row in result.mappings().all()
            ]

        encoded_rows = jsonable_encoder(rows)

        return {
            "generated_sql": sql_query,
            "row_count": len(encoded_rows),
            "results": encoded_rows,
            "answer": template["explanation"],
        }

    except SQLAlchemyError as error:
        print(f"Orchestrator SQL node failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="The SQL Agent failed inside the orchestrator.",
        )


# ---------------------------------------------------------
# NODE 3: RAG AGENT
# ---------------------------------------------------------
def rag_agent_node(
    state: OrchestratorState,
) -> OrchestratorState:
    """
    Execute the existing RAG Agent.
    """

    question = state["question"]

    chunks = retrieve_policy_chunks(
        question=question,
        top_k=3,
    )

    if not chunks:
        return {
            "answer": (
                "I could not find relevant information in the "
                "HR policy documents."
            ),
            "sources": [],
        }

    prompt = build_llama_prompt(
        question=question,
        chunks=chunks,
    )

    answer = call_rag_llama(prompt)

    return {
        "answer": answer,
        "sources": jsonable_encoder(chunks),
    }


# ---------------------------------------------------------
# NODE 4: ANALYTICS AGENT
# ---------------------------------------------------------
def analytics_agent_node(
    state: OrchestratorState,
) -> OrchestratorState:
    """
    Execute the Analytics Agent based on the question type.
    """

    question = state["question"]
    question_lower = question.lower()

    # Attendance risk questions
    if (
        "attendance risk" in question_lower
        or "attendance" in question_lower and "risk" in question_lower
        or "late" in question_lower
        or "absent risk" in question_lower
    ):
        analytics_response = get_attendance_risk(
            top_n=10,
            contamination=0.15,
        )

        return {
            "analysis_name": analytics_response.analysis_name,
            "answer": analytics_response.explanation,
            "row_count": analytics_response.row_count,
            "results": analytics_response.results,
        }

    # Payroll anomaly questions
    if (
        "payroll anomaly" in question_lower
        or "payroll anomalies" in question_lower
        or "unusual payroll" in question_lower
        or "salary anomaly" in question_lower
        or "salary anomalies" in question_lower
    ):
        analytics_response = get_payroll_anomalies(
            top_n=10,
            contamination=0.10,
        )

        return {
            "analysis_name": analytics_response.analysis_name,
            "answer": analytics_response.explanation,
            "row_count": analytics_response.row_count,
            "results": analytics_response.results,
        }

    # Department scorecard questions
    if (
        "department scorecard" in question_lower
        or "scorecard" in question_lower
        or "department analytics" in question_lower
        or "department analysis" in question_lower
    ):
        analytics_response = get_department_scorecard()

        return {
            "analysis_name": analytics_response.analysis_name,
            "answer": analytics_response.explanation,
            "row_count": analytics_response.row_count,
            "results": analytics_response.results,
        }

    # Default analytics route:
    # If analytics was selected but the exact type is unclear,
    # return department scorecard as a safe summary.
    analytics_response = get_department_scorecard()

    return {
        "analysis_name": analytics_response.analysis_name,
        "answer": (
            "The question was routed to Analytics Agent. "
            "Since the specific analysis type was unclear, "
            "a department scorecard was returned."
        ),
        "row_count": analytics_response.row_count,
        "results": analytics_response.results,
    }


# ---------------------------------------------------------
# BUILD LANGGRAPH WORKFLOW
# ---------------------------------------------------------
def build_orchestrator_graph():
    """
    Build and compile the LangGraph workflow.
    """

    graph_builder = StateGraph(OrchestratorState)

    # Add workflow nodes.
    graph_builder.add_node(
        "route_question",
        route_question_node,
    )

    graph_builder.add_node(
        "sql_agent",
        sql_agent_node,
    )

    graph_builder.add_node(
        "rag_agent",
        rag_agent_node,
    )

    graph_builder.add_node(
        "analytics_agent",
        analytics_agent_node,
    )

    # START means this is the first node that runs.
    graph_builder.add_edge(
        START,
        "route_question",
    )

    # After route_question, choose SQL, RAG, or Analytics.
    graph_builder.add_conditional_edges(
        "route_question",
        choose_next_agent,
        {
            "sql_agent": "sql_agent",
            "rag_agent": "rag_agent",
            "analytics_agent": "analytics_agent",
        },
    )

    # After each agent finishes, end the graph.
    graph_builder.add_edge(
        "sql_agent",
        END,
    )

    graph_builder.add_edge(
        "rag_agent",
        END,
    )

    graph_builder.add_edge(
        "analytics_agent",
        END,
    )

    return graph_builder.compile()


# Compile graph once when the application starts.
orchestrator_graph = build_orchestrator_graph()


# ---------------------------------------------------------
# FASTAPI ENDPOINT
# ---------------------------------------------------------
@router.post(
    "/ask",
    response_model=OrchestratorResponse,
)
def ask_orchestrator(
    request: OrchestratorRequest,
) -> OrchestratorResponse:
    """
    Ask one question and let LangGraph route it to the correct agent.
    """

    final_state = orchestrator_graph.invoke(
        {
            "question": request.question,
        }
    )

    return OrchestratorResponse(
        question=request.question,
        selected_agent=final_state["selected_agent"],
        route_reason=final_state["route_reason"],
        answer_type=final_state["answer_type"],
        generated_sql=final_state.get("generated_sql"),
        row_count=final_state.get("row_count"),
        results=final_state.get("results"),
        answer=final_state.get("answer"),
        sources=final_state.get("sources"),
        analysis_name=final_state.get("analysis_name"),
    )