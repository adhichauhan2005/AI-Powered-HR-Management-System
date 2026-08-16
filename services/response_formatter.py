from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

MAXIMUM_VISIBLE_ROWS = 10


# Words suggesting that a numeric value should
# be displayed using two decimal places.
MONEY_WORDS = {
    "salary",
    "pay",
    "bonus",
    "deduction",
    "tax",
    "cost",
    "amount",
    "allowance",
    "earnings",
}


# ---------------------------------------------------------
# KEY FORMATTING
# ---------------------------------------------------------

def format_key(
    key: str,
) -> str:
    """
    Convert a database column name into a readable label.

    employee_name
    becomes:
    Employee Name
    """

    return (
        key
        .replace("_", " ")
        .strip()
        .title()
    )


# ---------------------------------------------------------
# VALUE FORMATTING
# ---------------------------------------------------------

def format_value(
    key: str,
    value: Any,
) -> str:
    """
    Convert a database value into customer-friendly text.
    """

    if value is None:
        return "Not available"

    if isinstance(
        value,
        (date, datetime),
    ):
        return value.isoformat()

    key_lower = key.casefold()

    is_money_column = any(
        money_word in key_lower
        for money_word in MONEY_WORDS
    )

    if (
        isinstance(
            value,
            (int, float, Decimal),
        )
        and is_money_column
    ):
        return f"{value:,.2f}"

    return str(value)


# ---------------------------------------------------------
# ONE RESULT ROW
# ---------------------------------------------------------

def format_result_row(
    row: dict[str, Any],
    row_number: int,
) -> str:
    """
    Convert one result dictionary into readable text.
    """

    formatted_parts = []

    for key, value in row.items():

        readable_key = format_key(
            key
        )

        readable_value = format_value(
            key=key,
            value=value,
        )

        formatted_parts.append(
            f"{readable_key}: "
            f"{readable_value}"
        )

    joined_parts = " | ".join(
        formatted_parts
    )

    return (
        f"{row_number}. "
        f"{joined_parts}"
    )


# ---------------------------------------------------------
# MULTIPLE RESULT ROWS
# ---------------------------------------------------------

def format_result_rows(
    rows: list[dict[str, Any]],
) -> str:
    """
    Format up to ten result rows.

    We limit the visible records so the customer
    interface does not become overloaded.
    """

    if not rows:
        return "I found no matching records."

    visible_rows = rows[
        :MAXIMUM_VISIBLE_ROWS
    ]

    formatted_rows = []

    for row_number, row in enumerate(
        visible_rows,
        start=1,
    ):

        formatted_row = format_result_row(
            row=row,
            row_number=row_number,
        )

        formatted_rows.append(
            formatted_row
        )

    if (
        len(rows)
        > MAXIMUM_VISIBLE_ROWS
    ):

        formatted_rows.append(
            "Showing "
            f"{MAXIMUM_VISIBLE_ROWS} "
            f"of {len(rows)} "
            "matching records."
        )

    return "\n".join(
        formatted_rows
    )


# ---------------------------------------------------------
# MAIN ORCHESTRATOR FORMATTER
# ---------------------------------------------------------

def format_orchestrator_result(
    orchestrator_result: dict[str, Any],
) -> str:
    """
    Convert the LangGraph final state into one
    customer-friendly answer.

    The function intentionally does not display:

    - generated_sql
    - selected_agent
    - route_reason
    - answer_type
    - RAG source dictionaries
    """

    answer = orchestrator_result.get(
        "answer"
    )

    results = (
        orchestrator_result.get(
            "results"
        )
        or []
    )

    # RAG commonly provides a complete answer and
    # no structured result rows.
    if (
        isinstance(answer, str)
        and answer.strip()
        and not results
    ):
        return answer.strip()

    formatted_rows = format_result_rows(
        results
    )

    # SQL and Analytics may provide both an explanation
    # and structured result rows.
    if (
        isinstance(answer, str)
        and answer.strip()
        and results
    ):

        return (
            f"{answer.strip()}\n\n"
            f"{formatted_rows}"
        )

    if results:
        return formatted_rows

    return (
        "I could not find enough information "
        "to answer that question."
    )