import os
import re
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine


load_dotenv()


router = APIRouter(
    prefix="/sql-agent",
    tags=["SQL Agent Llama"],
)


# ---------------------------------------------------------
# REQUEST AND RESPONSE MODELS
# ---------------------------------------------------------
class LlamaSQLRequest(BaseModel):
    question: str


class LlamaSQLResponse(BaseModel):
    question: str
    generated_sql: str
    row_count: int
    results: list[dict[str, Any]]


# ---------------------------------------------------------
# DATABASE SCHEMA CONTEXT FOR THE LLM
# ---------------------------------------------------------
SCHEMA_CONTEXT = """
You are generating MySQL SELECT queries for an HR database.

Database name: HRManagementDB

Tables and important columns:

Department:
- department_id
- department_code
- department_name
- location
- annual_budget
- department_status
- manager_employee_id

Employee:
- employee_id
- employee_code
- first_name
- last_name
- gender
- email
- phone
- city
- state
- hire_date
- employment_type
- job_title
- department_id
- manager_id
- work_location
- employee_status

Attendance:
- attendance_id
- employee_id
- attendance_date
- check_in_time
- check_out_time
- work_hours
- attendance_status
- shift_name
- work_mode
- late_minutes
- overtime_hours
- approved_by

LeaveRequest:
- leave_id
- employee_id
- leave_type
- start_date
- end_date
- total_days
- reason
- request_date
- leave_status
- approved_by
- approval_date
- is_paid

Payroll:
- payroll_id
- employee_id
- pay_period_start
- pay_period_end
- basic_salary
- housing_allowance
- other_allowances
- bonus
- overtime_pay
- deductions
- tax_amount
- net_salary
- payment_date
- payment_method
- currency
- payroll_status

Training:
- training_id
- employee_id
- training_name
- provider
- training_category
- start_date
- end_date
- duration_hours
- delivery_mode
- training_cost
- training_status
- score
- certificate_issued

PerformanceReview:
- review_id
- employee_id
- reviewer_id
- review_period_start
- review_period_end
- review_date
- goals_rating
- technical_rating
- communication_rating
- teamwork_rating
- leadership_rating
- overall_rating
- promotion_recommended
- review_status

JobHistory:
- job_history_id
- employee_id
- department_id
- job_title
- start_date
- end_date
- employment_type
- manager_id
- work_location
- job_grade
- annual_salary
- change_reason
- is_current

Skills:
- skill_record_id
- employee_id
- skill_name
- skill_category
- proficiency_level
- years_experience
- last_used_date
- is_primary_skill
- verified_by

Certifications:
- certification_id
- employee_id
- certification_name
- issuing_organization
- credential_id
- issue_date
- expiry_date
- certification_status
- skill_category
- renewal_required
- renewal_status

Rules:
1. Generate only one MySQL SELECT query.
2. Do not generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or TRUNCATE.
3. Do not use markdown.
4. Do not explain the SQL.
5. Return only the SQL query.
6. Use LIMIT 20 unless the question clearly asks for a summary.
7. Use JOINs when readable names are needed.
"""


# ---------------------------------------------------------
# BUILD PROMPT
# ---------------------------------------------------------
def build_sql_prompt(question: str) -> str:
    """
    Create a controlled prompt for the Llama model.
    """

    return f"""
{SCHEMA_CONTEXT}

User question:
{question}

Return only the SQL query.
"""


# ---------------------------------------------------------
# CALL OLLAMA
# ---------------------------------------------------------
def call_ollama(prompt: str) -> str:
    """
    Send the prompt to local Ollama and return the model response.
    """

    ollama_base_url = os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )

    ollama_model = os.getenv(
        "OLLAMA_MODEL",
        "llama3.2",
    )

    url = f"{ollama_base_url}/api/generate"

    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=120,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not connect to Ollama. "
                "Make sure Ollama is installed, running, "
                "and the model is downloaded."
            ),
        ) from error

    response_json = response.json()

    generated_text = response_json.get("response", "")

    if not generated_text.strip():
        raise HTTPException(
            status_code=500,
            detail="Ollama returned an empty response.",
        )

    return generated_text.strip()


# ---------------------------------------------------------
# CLEAN SQL OUTPUT
# ---------------------------------------------------------
def clean_generated_sql(raw_sql: str) -> str:
    """
    Remove markdown fences and extra text if the model adds them.
    """

    cleaned = raw_sql.strip()

    cleaned = cleaned.replace("```sql", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.strip()

    # Keep only from the first SELECT onward.
    match = re.search(
        r"select\s+",
        cleaned,
        flags=re.IGNORECASE,
    )

    if match:
        cleaned = cleaned[match.start():]

    # Keep only the first statement.
    if ";" in cleaned:
        cleaned = cleaned.split(";")[0] + ";"

    return cleaned.strip()


# ---------------------------------------------------------
# SQL SAFETY CHECK
# ---------------------------------------------------------
def validate_llm_sql(sql: str) -> None:
    """
    Validate that the generated SQL is read-only and safe.
    """

    lowered = sql.lower().strip()

    if not lowered.startswith("select"):
        raise HTTPException(
            status_code=400,
            detail="Generated SQL was not a SELECT query.",
        )

    blocked_keywords = [
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "truncate",
        "replace",
        "merge",
        "grant",
        "revoke",
    ]

    for keyword in blocked_keywords:
        if re.search(rf"\\b{keyword}\\b", lowered):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsafe SQL keyword detected: {keyword}"
                ),
            )

    # Avoid multiple statements.
    if lowered.count(";") > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple SQL statements are not allowed.",
        )


# ---------------------------------------------------------
# MAIN LLAMA SQL AGENT ENDPOINT
# ---------------------------------------------------------
@router.post(
    "/llama-ask",
    response_model=LlamaSQLResponse,
)
def ask_llama_sql_agent(
    request: LlamaSQLRequest,
) -> LlamaSQLResponse:
    """
    Use Llama to generate a SQL query, validate it, run it,
    and return the result.
    """

    prompt = build_sql_prompt(request.question)

    raw_sql = call_ollama(prompt)

    generated_sql = clean_generated_sql(raw_sql)

    validate_llm_sql(generated_sql)

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(generated_sql)
            )

            rows = [
                dict(row)
                for row in result.mappings().all()
            ]

        encoded_rows = jsonable_encoder(rows)

        return LlamaSQLResponse(
            question=request.question,
            generated_sql=generated_sql,
            row_count=len(encoded_rows),
            results=encoded_rows,
        )

    except SQLAlchemyError as error:
        print(f"Llama SQL execution failed: {error}")

        raise HTTPException(
            status_code=500,
            detail=(
                "The generated SQL could not be executed. "
                "Try rephrasing the question."
            ),
        )