from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics Agent"],
)


class AnalyticsResponse(BaseModel):
    analysis_name: str
    explanation: str
    row_count: int
    results: list[dict[str, Any]]


def read_dataframe(sql_query: str) -> pd.DataFrame:
    """
    Run a SQL query against MySQL and return the result
    as a pandas DataFrame.
    """

    try:
        with engine.connect() as connection:
            dataframe = pd.read_sql_query(text(sql_query), connection)

        return dataframe

    except Exception as error:
        print("DATABASE ERROR IN ANALYTICS AGENT:")
        print(error)

        raise HTTPException(
            status_code=500,
            detail=f"Could not read data from MySQL: {error}",
        )

def add_anomaly_scores(
    dataframe: pd.DataFrame,
    feature_columns: list[str],
    contamination: float,
) -> pd.DataFrame:
    """
    Add anomaly labels and scores using IsolationForest.
    """

    dataframe = dataframe.copy()

    if dataframe.empty:
        return dataframe

    features = dataframe[feature_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    features = features.fillna(0)

    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)

    model = IsolationForest(
        contamination=contamination,
        random_state=42,
    )

    predictions = model.fit_predict(scaled_features)

    anomaly_scores = -model.decision_function(scaled_features)

    dataframe["anomaly_label"] = [
        "Anomaly" if prediction == -1 else "Normal"
        for prediction in predictions
    ]

    dataframe["anomaly_score"] = anomaly_scores.round(4)

    dataframe["risk_rank"] = dataframe["anomaly_score"].rank(
        ascending=False,
        method="first",
    ).astype(int)

    return dataframe


def dataframe_to_records(
    dataframe: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Convert pandas DataFrame to JSON-safe records.
    """

    cleaned_dataframe = dataframe.copy()

    cleaned_dataframe = cleaned_dataframe.where(
        pd.notnull(cleaned_dataframe),
        None,
    )

    records = cleaned_dataframe.to_dict(orient="records")

    return jsonable_encoder(records)


@router.get(
    "/attendance-risk",
    response_model=AnalyticsResponse,
)
def get_attendance_risk(
    top_n: int = Query(
        default=10,
        ge=1,
        le=50,
    ),
    contamination: float = Query(
        default=0.15,
        ge=0.01,
        le=0.5,
    ),
) -> AnalyticsResponse:
    """
    Find employees with unusual attendance behavior.
    """

    sql_query = """
        SELECT
            e.employee_id,
            e.employee_code,
            CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
            d.department_name,

            COUNT(a.attendance_id) AS total_attendance_days,

            SUM(
                CASE
                    WHEN a.attendance_status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent_days,

            SUM(
                CASE
                    WHEN a.late_minutes > 0
                    THEN 1
                    ELSE 0
                END
            ) AS late_days,

            ROUND(SUM(a.late_minutes), 2) AS total_late_minutes,
            ROUND(SUM(a.overtime_hours), 2) AS total_overtime_hours,
            ROUND(AVG(a.work_hours), 2) AS average_work_hours

        FROM Employee AS e

        INNER JOIN Department AS d
            ON e.department_id = d.department_id

        LEFT JOIN Attendance AS a
            ON e.employee_id = a.employee_id

        GROUP BY
            e.employee_id,
            e.employee_code,
            e.first_name,
            e.last_name,
            d.department_name

        ORDER BY e.employee_id;
    """

    dataframe = read_dataframe(sql_query)

    if dataframe.empty:
        return AnalyticsResponse(
            analysis_name="attendance_risk",
            explanation="No attendance data was available.",
            row_count=0,
            results=[],
        )

    total_days = dataframe["total_attendance_days"].replace(
        0,
        1,
    )

    dataframe["absent_rate"] = (
        dataframe["absent_days"] / total_days
    ).round(4)

    dataframe["late_rate"] = (
        dataframe["late_days"] / total_days
    ).round(4)

    feature_columns = [
        "absent_days",
        "late_days",
        "total_late_minutes",
        "total_overtime_hours",
        "average_work_hours",
        "absent_rate",
        "late_rate",
    ]

    dataframe = add_anomaly_scores(
        dataframe=dataframe,
        feature_columns=feature_columns,
        contamination=contamination,
    )

    dataframe = dataframe.sort_values(
        by="anomaly_score",
        ascending=False,
    ).head(top_n)

    return AnalyticsResponse(
        analysis_name="attendance_risk",
        explanation=(
            "Employees are ranked using attendance-related features. "
            "Anomaly means the employee has an unusual attendance pattern."
        ),
        row_count=len(dataframe),
        results=dataframe_to_records(dataframe),
    )


@router.get(
    "/payroll-anomalies",
    response_model=AnalyticsResponse,
)
def get_payroll_anomalies(
    top_n: int = Query(
        default=10,
        ge=1,
        le=50,
    ),
    contamination: float = Query(
        default=0.10,
        ge=0.01,
        le=0.5,
    ),
) -> AnalyticsResponse:
    """
    Find employees with unusual payroll patterns.
    """

    sql_query = """
        SELECT
            e.employee_id,
            e.employee_code,
            CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
            d.department_name,
            e.job_title,

            COUNT(p.payroll_id) AS payroll_records,

            ROUND(AVG(p.net_salary), 2) AS average_net_salary,
            ROUND(SUM(p.bonus), 2) AS total_bonus,
            ROUND(SUM(p.overtime_pay), 2) AS total_overtime_pay,
            ROUND(SUM(p.deductions), 2) AS total_deductions,
            ROUND(SUM(p.tax_amount), 2) AS total_tax_amount

        FROM Employee AS e

        INNER JOIN Department AS d
            ON e.department_id = d.department_id

        LEFT JOIN Payroll AS p
            ON e.employee_id = p.employee_id

        GROUP BY
            e.employee_id,
            e.employee_code,
            e.first_name,
            e.last_name,
            d.department_name,
            e.job_title

        ORDER BY e.employee_id;
    """

    dataframe = read_dataframe(sql_query)

    if dataframe.empty:
        return AnalyticsResponse(
            analysis_name="payroll_anomalies",
            explanation="No payroll data was available.",
            row_count=0,
            results=[],
        )

    feature_columns = [
        "average_net_salary",
        "total_bonus",
        "total_overtime_pay",
        "total_deductions",
        "total_tax_amount",
    ]

    dataframe = add_anomaly_scores(
        dataframe=dataframe,
        feature_columns=feature_columns,
        contamination=contamination,
    )

    dataframe = dataframe.sort_values(
        by="anomaly_score",
        ascending=False,
    ).head(top_n)

    return AnalyticsResponse(
        analysis_name="payroll_anomalies",
        explanation=(
            "Employees are ranked using payroll-related features. "
            "Anomaly means the payroll pattern is unusual compared with others."
        ),
        row_count=len(dataframe),
        results=dataframe_to_records(dataframe),
    )


@router.get(
    "/department-scorecard",
    response_model=AnalyticsResponse,
)
def get_department_scorecard() -> AnalyticsResponse:
    """
    Create department-level HR analytics summary.
    """

    sql_query = """
        WITH attendance_summary AS (
            SELECT
                employee_id,
                COUNT(*) AS attendance_days,
                SUM(
                    CASE
                        WHEN attendance_status = 'Absent'
                        THEN 1
                        ELSE 0
                    END
                ) AS absent_days,
                SUM(overtime_hours) AS overtime_hours
            FROM Attendance
            GROUP BY employee_id
        ),

        payroll_summary AS (
            SELECT
                employee_id,
                SUM(net_salary) AS total_net_salary
            FROM Payroll
            GROUP BY employee_id
        ),

        performance_summary AS (
            SELECT
                employee_id,
                AVG(overall_rating) AS average_rating
            FROM PerformanceReview
            GROUP BY employee_id
        ),

        training_summary AS (
            SELECT
                employee_id,
                SUM(
                    CASE
                        WHEN training_status = 'Completed'
                        THEN 1
                        ELSE 0
                    END
                ) AS completed_trainings
            FROM Training
            GROUP BY employee_id
        )

        SELECT
            d.department_id,
            d.department_name,
            e.employee_id,

            COALESCE(a.attendance_days, 0) AS attendance_days,
            COALESCE(a.absent_days, 0) AS absent_days,
            COALESCE(a.overtime_hours, 0) AS overtime_hours,

            COALESCE(p.total_net_salary, 0) AS total_net_salary,

            ps.average_rating,

            COALESCE(t.completed_trainings, 0) AS completed_trainings

        FROM Department AS d

        LEFT JOIN Employee AS e
            ON d.department_id = e.department_id

        LEFT JOIN attendance_summary AS a
            ON e.employee_id = a.employee_id

        LEFT JOIN payroll_summary AS p
            ON e.employee_id = p.employee_id

        LEFT JOIN performance_summary AS ps
            ON e.employee_id = ps.employee_id

        LEFT JOIN training_summary AS t
            ON e.employee_id = t.employee_id;
    """

    dataframe = read_dataframe(sql_query)

    if dataframe.empty:
        return AnalyticsResponse(
            analysis_name="department_scorecard",
            explanation="No department data was available.",
            row_count=0,
            results=[],
        )

    scorecard = (
        dataframe.groupby(
            ["department_id", "department_name"],
            as_index=False,
        )
        .agg(
            employee_count=("employee_id", "nunique"),
            total_attendance_days=("attendance_days", "sum"),
            total_absent_days=("absent_days", "sum"),
            total_overtime_hours=("overtime_hours", "sum"),
            total_net_salary=("total_net_salary", "sum"),
            average_performance_rating=("average_rating", "mean"),
            completed_trainings=("completed_trainings", "sum"),
        )
    )

    scorecard["absence_rate"] = (
        scorecard["total_absent_days"]
        / scorecard["total_attendance_days"].replace(0, 1)
    ).round(4)

    scorecard["average_performance_rating"] = (
        scorecard["average_performance_rating"].round(2)
    )

    scorecard["total_overtime_hours"] = (
        scorecard["total_overtime_hours"].round(2)
    )

    scorecard["total_net_salary"] = (
        scorecard["total_net_salary"].round(2)
    )

    scorecard = scorecard.sort_values(
        by="employee_count",
        ascending=False,
    )

    return AnalyticsResponse(
        analysis_name="department_scorecard",
        explanation=(
            "Department-level scorecard created using pandas grouping "
            "and aggregation."
        ),
        row_count=len(scorecard),
        results=dataframe_to_records(scorecard),
    )