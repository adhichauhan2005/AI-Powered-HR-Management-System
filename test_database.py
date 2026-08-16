import os
import sys

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


# Load settings stored in the .env file.
load_dotenv()


def get_required_setting(setting_name: str) -> str:
    """
    Return a required configuration value.

    The program stops with a clear message when a setting
    is missing from the .env file.
    """
    value = os.getenv(setting_name)

    if not value:
        raise ValueError(
            f"{setting_name} is missing. Check the .env file."
        )

    return value


try:
    db_host = get_required_setting("DB_HOST")
    db_port = int(get_required_setting("DB_PORT"))
    db_user = get_required_setting("DB_USER")
    db_password = get_required_setting("DB_PASSWORD")
    db_name = get_required_setting("DB_NAME")

except ValueError as error:
    print(f"Configuration error: {error}")
    sys.exit(1)


# Build a secure database connection address.
database_url = URL.create(
    drivername="mysql+mysqlconnector",
    username=db_user,
    password=db_password,
    host=db_host,
    port=db_port,
    database=db_name,
)


# Create the database connection manager.
engine = create_engine(
    database_url,
    pool_pre_ping=True,
)


# Query 1: Count all employees.
employee_count_query = text(
    """
    SELECT COUNT(*) AS employee_count
    FROM Employee;
    """
)


# Query 2: Join Employee and Department and return five employees.
employee_query = text(
    """
    SELECT
        e.employee_id,
        e.employee_code,
        CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
        e.job_title,
        d.department_name,
        e.employee_status
    FROM Employee AS e
    INNER JOIN Department AS d
        ON e.department_id = d.department_id
    ORDER BY e.employee_id
    LIMIT 5;
    """
)


try:
    # Open a connection to MySQL.
    with engine.connect() as connection:
        print("Connected to MySQL successfully.\n")

        # Load the employee count into a pandas DataFrame.
        count_dataframe = pd.read_sql_query(
            employee_count_query,
            connection,
        )

        # Load five employee records into another DataFrame.
        employee_dataframe = pd.read_sql_query(
            employee_query,
            connection,
        )

        employee_count = count_dataframe.loc[
            0, "employee_count"
        ]

        print(f"Total employees: {employee_count}\n")

        print("First five employees:")
        print(employee_dataframe.to_string(index=False))


except SQLAlchemyError as error:
    print("Could not connect to the MySQL database.")
    print(f"Database error: {error}")
    sys.exit(1)


finally:
    # Release database connections.
    engine.dispose()