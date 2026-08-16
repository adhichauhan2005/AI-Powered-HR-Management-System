from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine
from query_loader import load_query_config

# All endpoints in this file will begin with /departments.
router = APIRouter(
    prefix="/departments",
    tags=["Departments"],
)

DEPARTMENT_QUERIES = load_query_config(
    "department_queries.yaml"
)

# ---------------------------------------------------------
# RESPONSE MODELS
# ---------------------------------------------------------
class DepartmentSummary(BaseModel):
    department_id: int
    department_code: str
    department_name: str
    location: str
    annual_budget: float
    department_status: str
    employee_count: int


class DepartmentDetail(DepartmentSummary):
    description: str | None = None
    cost_center: str | None = None
    manager_name: str | None = None
    phone_extension: str | None = None
    email_alias: str | None = None
    established_date: date | None = None


# ---------------------------------------------------------
# GET ALL DEPARTMENTS
# ---------------------------------------------------------
@router.get(
    "",
    response_model=list[DepartmentSummary],
)
def get_departments() -> list[dict[str, Any]]:
    """
    Return all departments with their employee counts.
    """

    query = text(
    DEPARTMENT_QUERIES["get_all_departments"]
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(query)

            departments = [
                dict(row)
                for row in result.mappings().all()
            ]

        return departments

    except SQLAlchemyError as error:
        print(f"Department query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve departments.",
        )


# ---------------------------------------------------------
# GET ONE DEPARTMENT
# ---------------------------------------------------------
@router.get(
    "/{department_id}",
    response_model=DepartmentDetail,
)
def get_department(
    department_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique department identifier",
        ),
    ],
) -> dict[str, Any]:
    """
    Return detailed information for one department.
    """

    query = text(
    DEPARTMENT_QUERIES["get_department_by_id"]
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(
                query,
                {
                    "department_id": department_id,
                },
            )

            department = result.mappings().first()

        if department is None:
            raise HTTPException(
                status_code=404,
                detail="Department not found.",
            )

        return dict(department)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Department detail query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve the department.",
        )