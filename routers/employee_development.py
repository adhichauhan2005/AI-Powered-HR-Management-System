from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine
from routers.employee_records import ensure_employee_exists
from query_loader import load_query_config


# Every route in this file starts with /employees.
router = APIRouter(
    prefix="/employees",
    tags=["Employee Development"],
)
EMPLOYEE_DEVELOPMENT_QUERIES = load_query_config(
    "employee_development_queries.yaml"
)


# =========================================================
# RESPONSE MODELS
# =========================================================

class TrainingRecord(BaseModel):
    training_id: int
    training_name: str
    provider: str
    training_category: str
    start_date: date
    end_date: date
    duration_hours: float
    delivery_mode: str
    training_cost: float
    training_status: str
    score: float | None = None
    certificate_issued: bool
    trainer_name: str | None = None
    employee_feedback: str | None = None


class PerformanceReviewRecord(BaseModel):
    review_id: int
    reviewer_id: int
    reviewer_name: str
    review_period_start: date
    review_period_end: date
    review_date: date
    goals_rating: float
    technical_rating: float
    communication_rating: float
    teamwork_rating: float
    leadership_rating: float
    overall_rating: float
    strengths: str | None = None
    improvement_areas: str | None = None
    next_period_goals: str | None = None
    promotion_recommended: bool
    review_status: str


class JobHistoryRecord(BaseModel):
    job_history_id: int
    department_id: int
    department_name: str
    job_title: str
    start_date: date
    end_date: date | None = None
    employment_type: str
    manager_id: int | None = None
    manager_name: str | None = None
    work_location: str
    job_grade: str
    annual_salary: float
    change_reason: str
    is_current: bool


class SkillRecord(BaseModel):
    skill_record_id: int
    skill_name: str
    skill_category: str
    proficiency_level: str
    years_experience: float
    last_used_date: date
    is_primary_skill: bool
    verified_by: int | None = None
    verifier_name: str | None = None
    verification_date: date | None = None
    notes: str | None = None


class CertificationRecord(BaseModel):
    certification_id: int
    certification_name: str
    issuing_organization: str
    credential_id: str
    issue_date: date
    expiry_date: date | None = None
    credential_url: str | None = None
    certification_status: str
    skill_category: str
    renewal_required: bool
    renewal_status: str
    verification_date: date | None = None
    notes: str | None = None


# =========================================================
# TRAINING ENDPOINT
# =========================================================

@router.get(
    "/{employee_id}/training",
    response_model=list[TrainingRecord],
)
def get_employee_training(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    status: Annotated[
        Literal[
            "Completed",
            "In Progress",
            "Enrolled",
            "Cancelled",
        ] | None,
        Query(
            description="Optional training-status filter",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum records to return",
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
    Return training records for one employee.
    """

    conditions = [
        "t.employee_id = :employee_id",
    ]

    parameters: dict[str, Any] = {
        "employee_id": employee_id,
        "limit": limit,
        "offset": offset,
    }

    if status is not None:
        conditions.append(
            "t.training_status = :status"
        )
        parameters["status"] = status

    where_clause = " AND ".join(conditions)

    query_template = EMPLOYEE_DEVELOPMENT_QUERIES[
    "training"
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

            records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Training query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve training records.",
        )


# =========================================================
# PERFORMANCE REVIEW ENDPOINT
# =========================================================

@router.get(
    "/{employee_id}/performance-reviews",
    response_model=list[PerformanceReviewRecord],
)
def get_employee_performance_reviews(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    status: Annotated[
        Literal[
            "Draft",
            "Submitted",
            "Completed",
        ] | None,
        Query(
            description="Optional review-status filter",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum records to return",
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
    Return performance reviews for one employee.
    """

    conditions = [
        "pr.employee_id = :employee_id",
    ]

    parameters: dict[str, Any] = {
        "employee_id": employee_id,
        "limit": limit,
        "offset": offset,
    }

    if status is not None:
        conditions.append(
            "pr.review_status = :status"
        )
        parameters["status"] = status

    where_clause = " AND ".join(conditions)

    query_template = EMPLOYEE_DEVELOPMENT_QUERIES[
    "performance_reviews"
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

            records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(
            f"Performance review query failed: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not retrieve performance reviews."
            ),
        )


# =========================================================
# JOB HISTORY ENDPOINT
# =========================================================

@router.get(
    "/{employee_id}/job-history",
    response_model=list[JobHistoryRecord],
)
def get_employee_job_history(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    current_only: Annotated[
        bool,
        Query(
            description=(
                "Return only the employee's current role"
            ),
        ),
    ] = False,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum records to return",
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
    Return previous and current job records.
    """

    conditions = [
        "jh.employee_id = :employee_id",
    ]

    parameters: dict[str, Any] = {
        "employee_id": employee_id,
        "limit": limit,
        "offset": offset,
    }

    if current_only:
        conditions.append(
            "jh.is_current = TRUE"
        )

    where_clause = " AND ".join(conditions)

    query_template = EMPLOYEE_DEVELOPMENT_QUERIES[
    "job_history"
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

            records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Job history query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve job history.",
        )


# =========================================================
# SKILLS ENDPOINT
# =========================================================

@router.get(
    "/{employee_id}/skills",
    response_model=list[SkillRecord],
)
def get_employee_skills(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    proficiency_level: Annotated[
        Literal[
            "Beginner",
            "Intermediate",
            "Advanced",
            "Expert",
        ] | None,
        Query(
            description=(
                "Optional skill proficiency filter"
            ),
        ),
    ] = None,
    primary_only: Annotated[
        bool,
        Query(
            description="Return only primary skills",
        ),
    ] = False,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum records to return",
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of records to skip",
        ),
    ] = 0,
) -> list[dict[str, Any]]:
    """
    Return skills assigned to one employee.
    """

    conditions = [
        "s.employee_id = :employee_id",
    ]

    parameters: dict[str, Any] = {
        "employee_id": employee_id,
        "limit": limit,
        "offset": offset,
    }

    if proficiency_level is not None:
        conditions.append(
            "s.proficiency_level = :proficiency_level"
        )

        parameters["proficiency_level"] = (
            proficiency_level
        )

    if primary_only:
        conditions.append(
            "s.is_primary_skill = TRUE"
        )

    where_clause = " AND ".join(conditions)

    query_template = EMPLOYEE_DEVELOPMENT_QUERIES[
    "skills"
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

            records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Skills query failed: {error}")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve employee skills.",
        )


# =========================================================
# CERTIFICATIONS ENDPOINT
# =========================================================

@router.get(
    "/{employee_id}/certifications",
    response_model=list[CertificationRecord],
)
def get_employee_certifications(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
    status: Annotated[
        Literal[
            "Active",
            "Expired",
            "Revoked",
            "Pending Verification",
        ] | None,
        Query(
            description=(
                "Optional certification-status filter"
            ),
        ),
    ] = None,
    renewal_required: Annotated[
        bool | None,
        Query(
            description=(
                "Optional renewal-required filter"
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
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of records to skip",
        ),
    ] = 0,
) -> list[dict[str, Any]]:
    """
    Return professional certifications for one employee.
    """

    conditions = [
        "c.employee_id = :employee_id",
    ]

    parameters: dict[str, Any] = {
        "employee_id": employee_id,
        "limit": limit,
        "offset": offset,
    }

    if status is not None:
        conditions.append(
            "c.certification_status = :status"
        )
        parameters["status"] = status

    if renewal_required is not None:
        conditions.append(
            "c.renewal_required = :renewal_required"
        )

        parameters["renewal_required"] = (
            renewal_required
        )

    where_clause = " AND ".join(conditions)

    query_template = EMPLOYEE_DEVELOPMENT_QUERIES[
    "certifications"
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

            records = [
                dict(row)
                for row in result.mappings().all()
            ]

        return records

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(
            f"Certification query failed: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not retrieve certifications."
            ),
        )