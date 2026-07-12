from pathlib import Path
from typing import Any, Dict, List, Optional
import re
import yaml

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine


router = APIRouter(
    prefix="/sql-agent",
    tags=["SQL Agent"],
)


TRAINING_FILE_PATH = Path("config/sql_agent_training.yaml")


class SQLAgentRequest(BaseModel):
    question: str


class SQLAgentResponse(BaseModel):
    question: str
    matched_intent: Optional[str]
    explanation: str
    generated_sql: Optional[str]
    row_count: int
    results: List[Dict[str, Any]]


def load_sql_agent_training() -> Dict[str, Any]:
    """
    Load SQL Agent training data from YAML.

    This keeps SQL examples and SQL templates outside Python code.
    """

    if not TRAINING_FILE_PATH.exists():
        return {
            "intents": {},
            "fallback": {
                "enabled": True,
                "message": "SQL Agent training file not found.",
            },
        }

    with open(TRAINING_FILE_PATH, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if data is None:
        data = {}

    return data


SQL_AGENT_TRAINING = load_sql_agent_training()


def build_query_templates(training_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Convert YAML intents into a Python dictionary.

    This keeps compatibility with orchestrator.py because orchestrator imports:
    QUERY_TEMPLATES
    """

    templates = {}

    intents = training_data.get("intents", {})

    for intent_name, intent_details in intents.items():
        templates[intent_name] = {
            "description": intent_details.get("description", ""),
            "examples": intent_details.get("examples", []),
            "sql": intent_details.get("sql", ""),
            "explanation": intent_details.get("description", ""),
        }

    return templates


QUERY_TEMPLATES = build_query_templates(SQL_AGENT_TRAINING)


def normalize_text(value: str) -> str:
    """
    Normalize text so matching becomes easier.
    """

    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", "", value)
    value = re.sub(r"\s+", " ", value)

    return value


def calculate_example_match_score(question: str, example: str) -> float:
    """
    Compare the user question with one YAML training example.

    Score closer to 1 means better match.
    """

    normalized_question = normalize_text(question)
    normalized_example = normalize_text(example)

    if normalized_question == normalized_example:
        return 1.0

    if normalized_example in normalized_question:
        return 0.90

    if normalized_question in normalized_example:
        return 0.85

    question_words = set(normalized_question.split())
    example_words = set(normalized_example.split())

    if not question_words or not example_words:
        return 0.0

    common_words = question_words.intersection(example_words)
    score = len(common_words) / len(example_words)

    return score


def detect_intent(question: str) -> Optional[str]:
    """
    Detect SQL intent using YAML examples.

    Example:
    'Show me total number of employees?'
    should match:
    total_employees
    """

    best_intent = None
    best_score = 0.0

    for intent_name, template in QUERY_TEMPLATES.items():
        examples = template.get("examples", [])

        for example in examples:
            score = calculate_example_match_score(question, example)

            if score > best_score:
                best_score = score
                best_intent = intent_name

    minimum_score_required = 0.45

    if best_score >= minimum_score_required:
        return best_intent

    return None


def validate_select_query(sql_query: str) -> str:
    """
    Allow only safe SELECT queries.

    This protects the database from dangerous operations.
    """

    cleaned_sql = sql_query.strip()

    if cleaned_sql.endswith(";"):
        cleaned_sql = cleaned_sql[:-1]

    lowered_sql = cleaned_sql.lower()

    if not lowered_sql.startswith("select"):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed.",
        )

    dangerous_keywords = [
        "delete",
        "drop",
        "update",
        "insert",
        "alter",
        "truncate",
        "create",
        "replace",
        "grant",
        "revoke",
    ]

    for keyword in dangerous_keywords:
        pattern = rf"\b{keyword}\b"

        if re.search(pattern, lowered_sql):
            raise HTTPException(
                status_code=400,
                detail=f"Dangerous SQL keyword blocked: {keyword}",
            )

    if ";" in cleaned_sql:
        raise HTTPException(
            status_code=400,
            detail="Multiple SQL statements are not allowed.",
        )

    return cleaned_sql


def run_sql_query(sql_query: str) -> List[Dict[str, Any]]:
    """
    Run SQL query on MySQL and return list of dictionaries.
    """

    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))
            rows = result.mappings().all()

        return [dict(row) for row in rows]

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while running SQL Agent query: {error}",
        )


@router.post(
    "/ask",
    response_model=SQLAgentResponse,
)
def ask_sql_agent(request: SQLAgentRequest) -> SQLAgentResponse:
    """
    Main SQL Agent endpoint.

    It:
    1. Reads the user question
    2. Matches it with YAML examples
    3. Picks the SQL template
    4. Validates SQL safety
    5. Runs SQL on MySQL
    6. Returns clean JSON result
    """

    question = request.question
    matched_intent = detect_intent(question)

    if matched_intent is None:
        fallback_message = SQL_AGENT_TRAINING.get(
            "fallback",
            {},
        ).get(
            "message",
            "I could not match your question to a trained SQL intent.",
        )

        return SQLAgentResponse(
            question=question,
            matched_intent=None,
            explanation=fallback_message,
            generated_sql=None,
            row_count=0,
            results=[],
        )

    sql_query = QUERY_TEMPLATES[matched_intent]["sql"]
    safe_sql = validate_select_query(sql_query)
    results = run_sql_query(safe_sql)

    explanation = QUERY_TEMPLATES[matched_intent].get(
        "description",
        "SQL query executed successfully.",
    )

    return SQLAgentResponse(
        question=question,
        matched_intent=matched_intent,
        explanation=explanation,
        generated_sql=safe_sql,
        row_count=len(results),
        results=results,
    )