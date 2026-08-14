from uuid import uuid4

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import make_url

from help_matcher.config import get_settings


def create_postgres_test_engine():
    database_name = f"test_{uuid4().hex}"
    database_url = make_url(get_settings().database_url)
    admin_url = database_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))

    engine = create_engine(database_url.set(database=database_name))
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    SQLModel.metadata.create_all(engine)
    return engine
