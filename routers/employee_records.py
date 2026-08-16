from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from database import engine
from query_loader import load_query_config


# All routes in this file start with /employees.
router = APIRouter(
    prefix="/employees",
    tags=["Employee Records"],
)
EMPLOYEE_RECORD_QUERIES = load_query_config(
    "employee_record_queries.yaml"
)


# ---------------------------------------------------------
# RESPONSE MODELS
# ---------------------------------------------------------
class AttendanceRecord(BaseModel):
    attendance_id: int
    attendance_date: date
    check_in_time: str | None = None
    check_out_time: str | None = None
    work_hours: float
    attendance_status: str
    shift_name: str
    work_mode: str
    late_minutes: int
    overtime_hours: float
    remarks: str | None = None
    approved_by: int | None = None


class PayrollRecord(BaseModel):
    payroll_id: int
    pay_period_start: date
    pay_period_end: date
    basic_salary: float
    housing_allowance: float
    other_allowances: float
    bonus: float
    overtime_pay: float
    deductions: float
    tax_amount: float
    net_salary: float
    payment_date: date
    payment_method: str
    currency: str
    payroll_status: str


class LeaveRequestRecord(BaseModel):
    leave_id: int
    leave_type: str
    start_date: date
    end_date: date
    total_days: int
    reason: str
    request_date: date
    leave_status: str
    approved_by: int | None = None
    approver_name: str | None = None
    approval_date: date | None = None
    manager_comments: str | None = None
    is_paid: bool
    contact_during_leave: str | None = None


# ---------------------------------------------------------
# EMPLOYEE EXISTENCE CHECK
# ---------------------------------------------------------
def ensure_employee_exists(
    connection: Connection,
    employee_id: int,
) -> None:
    """
    Confirm that the requested employee exists.

    This lets the API distinguish between:
    - an employee who exists but has no records, and
    - an employee who does not exist.
    """

    query = text(
        EMPLOYEE_RECORD_QUERIES["employee_exists"]
    )

    employee = connection.execute(
        query,
        {"employee_id": employee_id},
    ).scalar_one_or_none()

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not found.",
        )


# ---------------------------------------------------------
# GET EMPLOYEE ATTENDANCE
# ---------------------------------------------------------
@router.get(
    "/{employee_id}/attendance",
    response_model=list[AttendanceRecord],
)
def get_employee_attendance(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    start_date: Annotated[
        date | None,
        Query(
            description=(
                "Optional starting attendance date "
                "in YYYY-MM-DD format"
            ),
        ),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(
            description=(
                "Optional ending attendance date "
                "in YYYY-MM-DD format"
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum records to return",
        ),
    ] = 30,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of records to skip",
        ),
    ] = 0,
) -> list[dict[str, Any]]:
    """
    Return attendance records for one employee.

    Optional date filters and pagination are supported.
    """

    if (
        start_date is not None
        and end_date is not None
        and start_date > end_date
    ):
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date.",
        )

    conditions = [
        "a.employee_id = :employee_id",
    ]

    parameters: dict[str, Any] = {
        "employee_id": employee_id,
        "limit": limit,
        "offset": offset,
    }

    if start_date is not None:
        conditions.append(
            "a.attendance_date >= :start_date"
        )
        parameters["start_date"] = start_date

    if end_date is not None:
        conditions.append(
            "a.attendance_date <= :end_date"
        )
        parameters["end_date"] = end_date

    where_clause = " AND ".join(conditions)

    query_template = EMPLOYEE_RECORD_QUERIES["attendance"]

    query = text(
       query_template.format(
          where_clause=where_clause,
        )
    )

    try:
        with engine.connect() as connection:
            ensure_employee_exists(
                connection,
                employee_id,
            )

            result = connection.execute(
                query,
                parameters,
            )

            attendance_records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return attendance_records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Attendance query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve attendance records.",
        )


# ---------------------------------------------------------
# GET EMPLOYEE PAYROLL
# ---------------------------------------------------------
@router.get(
    "/{employee_id}/payroll",
    response_model=list[PayrollRecord],
)
def get_employee_payroll(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=24,
            description="Maximum payroll records to return",
        ),
    ] = 12,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of records to skip",
        ),
    ] = 0,
) -> list[dict[str, Any]]:
    """
    Return payroll records for one employee.
    """

    query = text(
        EMPLOYEE_RECORD_QUERIES["payroll"]
    )

    try:
        with engine.connect() as connection:
            ensure_employee_exists(
                connection,
                employee_id,
            )

            result = connection.execute(
                query,
                {
                    "employee_id": employee_id,
                    "limit": limit,
                    "offset": offset,
                },
            )

            payroll_records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return payroll_records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Payroll query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve payroll records.",
        )


# ---------------------------------------------------------
# GET EMPLOYEE LEAVE REQUESTS
# ---------------------------------------------------------
@router.get(
    "/{employee_id}/leave-requests",
    response_model=list[LeaveRequestRecord],
)
def get_employee_leave_requests(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    status: Annotated[
        Literal[
            "Approved",
            "Pending",
            "Rejected",
        ] | None,
        Query(
            description=(
                "Optional leave-status filter"
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum leave records to return",
        ),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of records to skip",
        ),
    ] = 0,
) -> list[dict[str, Any]]:
    """
    Return leave requests for one employee.

    Results can optionally be filtered by leave status.
    """

    conditions = [
        "leave_record.employee_id = :employee_id",
    ]

    parameters: dict[str, Any] = {
        "employee_id": employee_id,
        "limit": limit,
        "offset": offset,
    }

    if status is not None:
        conditions.append(
            "leave_record.leave_status = :status"
        )
        parameters["status"] = status

    where_clause = " AND ".join(conditions)

    query_template = EMPLOYEE_RECORD_QUERIES[
    "leave_requests"
]

    query = text(
        query_template.format(
           where_clause=where_clause,
        )
    )

    try:
        with engine.connect() as connection:
            ensure_employee_exists(
                connection,
                employee_id,
            )

            result = connection.execute(
                query,
                parameters,
            )

            leave_records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return leave_records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Leave query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve leave requests.",
        )