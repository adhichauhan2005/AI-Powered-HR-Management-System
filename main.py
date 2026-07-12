import time
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Path, Query, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


from database import engine
from routers.departments import router as departments_router
from routers.employee_records import (
    router as employee_records_router,
)
from routers.employee_development import (
    router as employee_development_router,
)
from routers.sql_agent import router as sql_agent_router
from routers.sql_agent_llama import (
    router as sql_agent_llama_router,
)
from routers.rag_agent import router as rag_agent_router
from routers.orchestrator import router as orchestrator_router
from routers.analytics_agent import router as analytics_agent_router
from routers.feedback import router as feedback_router
from routers.prompt_discovery import router as prompt_discovery_router
from fastapi.middleware.cors import CORSMiddleware
from routers.autofix import router as autofix_router

# ---------------------------------------------------------
# CREATE THE FASTAPI APPLICATION
# ---------------------------------------------------------
app = FastAPI(
    title="HR Employee Portal API",
    description=(
        "API for retrieving employee and HR information "
        "from HRManagementDB."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(departments_router)
app.include_router(employee_records_router)
app.include_router(employee_development_router)
app.include_router(sql_agent_router)
app.include_router(sql_agent_llama_router)
app.include_router(rag_agent_router)
app.include_router(orchestrator_router)
app.include_router(analytics_agent_router)
app.include_router(feedback_router)
app.include_router(prompt_discovery_router)
app.include_router(autofix_router)
# ---------------------------------------------------------
# RESPONSE MODEL
# ---------------------------------------------------------
class EmployeeSummary(BaseModel):
    employee_id: int
    employee_code: str
    employee_name: str
    job_title: str
    department_name: str
    employee_status: str
    manager_name: str | None = None


# ---------------------------------------------------------
# SIMPLE MIDDLEWARE
# ---------------------------------------------------------
@app.middleware("http")
async def add_process_time_header(
    request: Request,
    call_next,
):
    """
    Measure how long each API request takes.

    The duration is added to the response headers as
    X-Process-Time.
    """
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time

    response.headers["X-Process-Time"] = (
        f"{process_time:.6f}"
    )

    return response


# ---------------------------------------------------------
# ROOT ENDPOINT
# ---------------------------------------------------------
@app.get(
    "/",
    tags=["General"],
)
def root() -> dict[str, str]:
    """
    Confirm that the HR API server is running.
    """
    return {
        "message": "HR Employee Portal API is running."
    }


# ---------------------------------------------------------
# DATABASE HEALTH ENDPOINT
# ---------------------------------------------------------
@app.get(
    "/health",
    tags=["General"],
)
def health_check() -> dict[str, str]:
    """
    Check whether FastAPI can communicate with MySQL.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "api_status": "healthy",
            "database_status": "connected",
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="The database is currently unavailable.",
        )


# ---------------------------------------------------------
# LIST EMPLOYEES
# ---------------------------------------------------------
@app.get(
    "/employees",
    response_model=list[EmployeeSummary],
    tags=["Employees"],
)
def get_employees(
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum employees to return",
        ),
    ] = 10,
) -> list[dict]:
    """
    Return a limited list of employees.
    """
    query = text(
        """
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
            e.employee_status,
            CONCAT(
                m.first_name,
                ' ',
                m.last_name
            ) AS manager_name
        FROM Employee AS e
        INNER JOIN Department AS d
            ON e.department_id = d.department_id
        LEFT JOIN Employee AS m
            ON e.manager_id = m.employee_id
        ORDER BY e.employee_id
        LIMIT :limit;
        """
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(
                query,
                {"limit": limit},
            )

            employees = [
                dict(row)
                for row in result.mappings().all()
            ]

        return employees

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve employees.",
        )


# ---------------------------------------------------------
# GET ONE EMPLOYEE
# ---------------------------------------------------------
@app.get(
    "/employees/{employee_id}",
    response_model=EmployeeSummary,
    tags=["Employees"],
)
def get_employee(
    employee_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique employee identifier",
        ),
    ],
) -> dict:
    """
    Return one employee using employee_id.
    """
    query = text(
        """
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
            e.employee_status,
            CONCAT(
                m.first_name,
                ' ',
                m.last_name
            ) AS manager_name
        FROM Employee AS e
        INNER JOIN Department AS d
            ON e.department_id = d.department_id
        LEFT JOIN Employee AS m
            ON e.manager_id = m.employee_id
        WHERE e.employee_id = :employee_id;
        """
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(
                query,
                {"employee_id": employee_id},
            )

            employee = result.mappings().first()

        if employee is None:
            raise HTTPException(
                status_code=404,
                detail="Employee not found.",
            )

        return dict(employee)

    except HTTPException:
        raise

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve the employee.",
        )


# ---------------------------------------------------------
# START THE LOCAL SERVER
# ---------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )