import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL


# Load values from the .env file.
load_dotenv()


def get_required_setting(setting_name: str) -> str:
    """
    Read a required value from the .env file.

    Raise a clear error when the setting is missing.
    """
    value = os.getenv(setting_name)

    if not value:
        raise RuntimeError(
            f"{setting_name} is missing from the .env file."
        )

    return value


# Read MySQL connection settings.
DB_HOST = get_required_setting("DB_HOST")
DB_PORT = int(get_required_setting("DB_PORT"))
DB_USER = get_required_setting("DB_USER")
DB_PASSWORD = get_required_setting("DB_PASSWORD")
DB_NAME = get_required_setting("DB_NAME")


# Build the MySQL connection address.
DATABASE_URL = URL.create(
    drivername="mysql+mysqlconnector",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)


# Create one reusable SQLAlchemy Engine.
engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)