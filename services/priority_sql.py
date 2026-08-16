from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine

from services.context_layer import (
    ContextResolution,
)


# ---------------------------------------------------------
# LATEST PAYROLL SQL
# ---------------------------------------------------------

# One employee can have multiple payroll records.
#
# ROW_NUMBER ranks the payroll records separately
# for each employee.
#
# payroll_rank = 1 means:
# the latest payroll record for that employee.
LATEST_PAYROLL_CTE = """
    WITH latest_payroll AS
    (
        SELECT
            p.*,

            ROW_NUMBER() OVER
            (
                PARTITION BY p.employee_id

                ORDER BY
                    p.pay_period_end DESC,
                    p.payroll_id DESC
            ) AS payroll_rank

        FROM Payroll AS p
    )
"""


# ---------------------------------------------------------
# MONEY FORMATTING
# ---------------------------------------------------------

def format_money(
    value: Any,
    currency: str | None,
) -> str:
    """
    Format a database salary value.

    Example:

    value = 50000
    currency = USD

    Result:

    USD 50,000.00
    """

    if value is None:
        return "not available"

    decimal_value = Decimal(
        str(value)
    )

    currency_code = (
        currency
        or ""
    )

    formatted_value = (
        f"{decimal_value:,.2f}"
    )

    if currency_code:
        return (
            f"{currency_code} "
            f"{formatted_value}"
        )

    return formatted_value


# ---------------------------------------------------------
# SAFE DATABASE EXECUTION
# ---------------------------------------------------------

def run_priority_query(
    sql_query: str,
    parameters: dict[
        str,
        Any,
    ] | None = None,
) -> list[dict[str, Any]]:
    """
    Execute a predefined read-only SQL query.

    Parameter values are passed separately to SQLAlchemy.
    This protects job-title searches from SQL injection.
    """

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text(sql_query),
                parameters or {},
            )

            rows = result.mappings().all()

        return [
            dict(row)
            for row in rows
        ]

    except SQLAlchemyError as error:

        raise RuntimeError(
            "The priority SQL query failed. "
            f"Database error: {error}"
        ) from error


# ---------------------------------------------------------
# LOWEST OR HIGHEST SALARY
# ---------------------------------------------------------

def get_salary_superlative(
    direction: str,
) -> dict[str, Any]:
    """
    Return exactly one employee with the lowest
    or highest current basic salary.

    ASC:
    Lowest salary

    DESC:
    Highest salary
    """

    # Only ASC and DESC are allowed.
    #
    # Never insert an unrestricted user value
    # directly into SQL.
    if direction.upper() == "DESC":
        safe_direction = "DESC"

    else:
        safe_direction = "ASC"

    sql_query = f"""
        {LATEST_PAYROLL_CTE}

        SELECT
            e.employee_id,

            e.employee_code,

            CONCAT(
                e.first_name,
                ' ',
                e.last_name
            ) AS employee_name,

            e.job_title,

            d.department_name,

            lp.basic_salary,

            lp.currency,

            lp.pay_period_start,

            lp.pay_period_end

        FROM Employee AS e

        INNER JOIN latest_payroll AS lp
            ON e.employee_id = lp.employee_id
            AND lp.payroll_rank = 1

        LEFT JOIN Department AS d
            ON e.department_id = d.department_id

        ORDER BY
            lp.basic_salary {safe_direction},
            e.employee_id ASC

        LIMIT 1
    """

    rows = run_priority_query(
        sql_query=sql_query
    )

    if not rows:

        return {
            "answer": (
                "I could not find current payroll "
                "data for any employee."
            ),
            "row_count": 0,
            "rows": [],
        }

    # LIMIT 1 ensures rows[0] is the only record.
    employee_record = rows[0]

    if safe_direction == "DESC":
        salary_label = "highest"

    else:
        salary_label = "lowest"

    formatted_salary = format_money(
        value=employee_record[
            "basic_salary"
        ],
        currency=employee_record.get(
            "currency"
        ),
    )

    answer = (
        f"{employee_record['employee_name']} "
        f"has the {salary_label} current "
        f"basic salary: {formatted_salary}. "
        f"The employee's designation is "
        f"{employee_record['job_title']}, "
        f"and the latest payroll period ends "
        f"on {employee_record['pay_period_end']}."
    )

    return {
        "answer": answer,
        "row_count": 1,
        "rows": rows,
    }


# ---------------------------------------------------------
# SALARY BY JOB TITLE
# ---------------------------------------------------------

def get_salary_by_job_title(
    job_title: str,
) -> dict[str, Any]:
    """
    Find current salaries using Employee.job_title.

    Example:

    job_title = "AI Engineer"

    Search:

    WHERE LOWER(e.job_title)
          LIKE '%ai engineer%'
    """

    sql_query = f"""
        {LATEST_PAYROLL_CTE}

        SELECT
            e.employee_id,

            e.employee_code,

            CONCAT(
                e.first_name,
                ' ',
                e.last_name
            ) AS employee_name,

            e.job_title,

            d.department_name,

            lp.basic_salary,

            lp.net_salary,

            lp.currency,

            lp.pay_period_start,

            lp.pay_period_end

        FROM Employee AS e

        INNER JOIN latest_payroll AS lp
            ON e.employee_id = lp.employee_id
            AND lp.payroll_rank = 1

        LEFT JOIN Department AS d
            ON e.department_id = d.department_id

        WHERE LOWER(
            e.job_title
        ) LIKE :job_title_pattern

        ORDER BY
            e.employee_id ASC
    """

    query_parameters = {
        "job_title_pattern": (
            f"%{job_title.casefold()}%"
        )
    }

    rows = run_priority_query(
        sql_query=sql_query,
        parameters=query_parameters,
    )

    if not rows:

        return {
            "answer": (
                "I could not find an employee "
                "whose designation matches "
                f"'{job_title}'."
            ),
            "row_count": 0,
            "rows": [],
        }

    answer_lines = []

    for employee_record in rows:

        formatted_salary = format_money(
            value=employee_record[
                "basic_salary"
            ],
            currency=employee_record.get(
                "currency"
            ),
        )

        line = (
            f"{employee_record['employee_name']} "
            f"— {employee_record['job_title']} "
            f"— {formatted_salary}"
        )

        answer_lines.append(
            line
        )

    bullet_list = "\n".join(
        f"• {line}"
        for line in answer_lines
    )

    answer = (
        f"I found {len(rows)} employee(s) "
        f"whose designation matches "
        f"'{job_title}':\n"
        f"{bullet_list}"
    )

    return {
        "answer": answer,
        "row_count": len(rows),
        "rows": rows,
    }


# ---------------------------------------------------------
# MAIN PRIORITY SQL ROUTER
# ---------------------------------------------------------

def execute_priority_sql(
    resolution: ContextResolution,
) -> dict[str, Any]:
    """
    Execute the correct predefined SQL operation
    using the ContextResolution result.
    """

    if (
        resolution.action
        == "salary_superlative"
    ):

        direction = str(
            resolution.parameters.get(
                "direction",
                "ASC",
            )
        )

        return get_salary_superlative(
            direction=direction
        )

    if (
        resolution.action
        == "salary_by_job_title"
    ):

        job_title = str(
            resolution.parameters.get(
                "job_title",
                "",
            )
        ).strip()

        if not job_title:

            return {
                "answer": (
                    "I could not identify the "
                    "employee designation in "
                    "the question."
                ),
                "row_count": 0,
                "rows": [],
            }

        return get_salary_by_job_title(
            job_title=job_title
        )

    raise ValueError(
        "Unsupported priority SQL action: "
        f"{resolution.action}"
    )