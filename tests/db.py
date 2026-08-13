from uuid import uuid4

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from help_matcher.config import get_settings


def create_postgres_test_engine():
    schema_name = f"test_{uuid4().hex}"
    database_url = get_settings().database_url
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema_name},public"},
    )
    SQLModel.metadata.create_all(engine)
    return engine
