from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine


router = APIRouter(
    prefix="/sql-agent",
    tags=["SQL Agent"],
)


# ---------------------------------------------------------
# REQUEST AND RESPONSE MODELS
# ---------------------------------------------------------
class SQLAgentRequest(BaseModel):
    question: str


class SQLAgentResponse(BaseModel):
    question: str
    matched_intent: str
    explanation: str
    generated_sql: str
    row_count: int
    results: list[dict[str, Any]]


# ---------------------------------------------------------
# SAFE QUERY TEMPLATES
# ---------------------------------------------------------
QUERY_TEMPLATES: dict[str, dict[str, str]] = {
    "department_employee_count": {
        "explanation": "Shows employee count by department.",
        "sql": """
            SELECT
                d.department_name,
                COUNT(e.employee_id) AS employee_count
            FROM Department AS d
            LEFT JOIN Employee AS e
                ON d.department_id = e.department_id
            GROUP BY d.department_name
            ORDER BY employee_count DESC;
        """,
    },

    "department_payroll": {
        "explanation": "Shows total payroll amount by department.",
        "sql": """
            SELECT
                d.department_name,
                ROUND(SUM(p.net_salary), 2) AS total_net_salary
            FROM Payroll AS p
            INNER JOIN Employee AS e
                ON p.employee_id = e.employee_id
            INNER JOIN Department AS d
                ON e.department_id = d.department_id
            GROUP BY d.department_name
            ORDER BY total_net_salary DESC;
        """,
    },

    "top_absent_employees": {
        "explanation": "Shows employees with the highest number of absent days.",
        "sql": """
            SELECT
                e.employee_id,
                e.employee_code,
                CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                d.department_name,
                COUNT(a.attendance_id) AS absent_days
            FROM Attendance AS a
            INNER JOIN Employee AS e
                ON a.employee_id = e.employee_id
            INNER JOIN Department AS d
                ON e.department_id = d.department_id
            WHERE a.attendance_status = 'Absent'
            GROUP BY
                e.employee_id,
                e.employee_code,
                employee_name,
                d.department_name
            ORDER BY absent_days DESC
            LIMIT 10;
        """,
    },

    "highest_overtime": {
        "explanation": "Shows employees with the highest total overtime hours.",
        "sql": """
            SELECT
                e.employee_id,
                e.employee_code,
                CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                d.department_name,
                ROUND(SUM(a.overtime_hours), 2) AS total_overtime_hours
            FROM Attendance AS a
            INNER JOIN Employee AS e
                ON a.employee_id = e.employee_id
            INNER JOIN Department AS d
                ON e.department_id = d.department_id
            GROUP BY
                e.employee_id,
                e.employee_code,
                employee_name,
                d.department_name
            ORDER BY total_overtime_hours DESC
            LIMIT 10;
        """,
    },

    "training_completion": {
        "explanation": "Shows training completion count by department.",
        "sql": """
            SELECT
                d.department_name,
                COUNT(t.training_id) AS completed_trainings
            FROM Training AS t
            INNER JOIN Employee AS e
                ON t.employee_id = e.employee_id
            INNER JOIN Department AS d
                ON e.department_id = d.department_id
            WHERE t.training_status = 'Completed'
            GROUP BY d.department_name
            ORDER BY completed_trainings DESC;
        """,
    },

    "certification_status": {
        "explanation": "Shows certification count by status.",
        "sql": """
            SELECT
                certification_status,
                COUNT(*) AS certification_count
            FROM Certifications
            GROUP BY certification_status
            ORDER BY certification_count DESC;
        """,
    },

    "average_performance_by_department": {
        "explanation": "Shows average performance rating by department.",
        "sql": """
            SELECT
                d.department_name,
                ROUND(AVG(pr.overall_rating), 2) AS average_overall_rating
            FROM PerformanceReview AS pr
            INNER JOIN Employee AS e
                ON pr.employee_id = e.employee_id
            INNER JOIN Department AS d
                ON e.department_id = d.department_id
            GROUP BY d.department_name
            ORDER BY average_overall_rating DESC;
        """,
    },

    "employee_status_summary": {
        "explanation": "Shows employee count by employee status.",
        "sql": """
            SELECT
                employee_status,
                COUNT(*) AS employee_count
            FROM Employee
            GROUP BY employee_status
            ORDER BY employee_count DESC;
        """,
    },
}


# ---------------------------------------------------------
# SIMPLE INTENT DETECTION
# ---------------------------------------------------------
def detect_intent(question: str) -> str:
    """
    Detect the user's intent using simple keywords.

    Later, this function can be replaced with Llama.
    """

    question_lower = question.lower()

    if (
        "department" in question_lower
        and "employee" in question_lower
        and "count" in question_lower
    ):
        return "department_employee_count"

    if (
        "department" in question_lower
        and (
            "payroll" in question_lower
            or "salary" in question_lower
            or "highest paid" in question_lower
        )
    ):
        return "department_payroll"

    if (
        "absent" in question_lower
        or "absence" in question_lower
        or "most leave" in question_lower
    ):
        return "top_absent_employees"

    if (
        "overtime" in question_lower
        or "extra hours" in question_lower
    ):
        return "highest_overtime"

    if (
        "training" in question_lower
        and (
            "complete" in question_lower
            or "completion" in question_lower
        )
    ):
        return "training_completion"

    if "certification" in question_lower:
        return "certification_status"

    if (
        "performance" in question_lower
        or "rating" in question_lower
    ):
        return "average_performance_by_department"

    if (
        "employee status" in question_lower
        or "active employees" in question_lower
        or "on leave" in question_lower
    ):
        return "employee_status_summary"

    raise HTTPException(
        status_code=400,
        detail=(
            "I could not understand the question yet. "
            "Try asking about payroll, attendance, overtime, "
            "training, certifications, performance, or employee count."
        ),
    )


# ---------------------------------------------------------
# SQL SAFETY CHECK
# ---------------------------------------------------------
def validate_select_query(sql: str) -> None:
    """
    Allow only SELECT queries.

    This prevents dangerous operations such as DELETE, DROP,
    UPDATE, INSERT, and ALTER.
    """

    cleaned_sql = sql.strip().lower()

    if not cleaned_sql.startswith("select"):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed.",
        )

    blocked_words = [
        "delete",
        "drop",
        "update",
        "insert",
        "alter",
        "truncate",
        "create",
    ]

    for word in blocked_words:
        if word in cleaned_sql:
            raise HTTPException(
                status_code=400,
                detail=f"Unsafe SQL keyword detected: {word}",
            )


# ---------------------------------------------------------
# MAIN SQL AGENT ENDPOINT
# ---------------------------------------------------------
@router.post(
    "/ask",
    response_model=SQLAgentResponse,
)
def ask_sql_agent(
    request: SQLAgentRequest,
) -> SQLAgentResponse:
    """
    Accept a natural-language HR question, select a safe SQL
    query, execute it, and return the result.
    """

    intent = detect_intent(request.question)

    template = QUERY_TEMPLATES[intent]

    sql_query = template["sql"]

    validate_select_query(sql_query)

    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))

            rows = [
                dict(row)
                for row in result.mappings().all()
            ]

        encoded_rows = jsonable_encoder(rows)

        return SQLAgentResponse(
            question=request.question,
            matched_intent=intent,
            explanation=template["explanation"],
            generated_sql=sql_query.strip(),
            row_count=len(encoded_rows),
            results=encoded_rows,
        )

    except SQLAlchemyError as error:
        print(f"SQL Agent query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="The SQL Agent could not execute the query.",
        )