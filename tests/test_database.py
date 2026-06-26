from sqlalchemy import text

from eventcart.database import Base, create_database_engine


def test_database_metadata_can_create_schema() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(engine)

    with engine.connect() as connection:
        result = connection.execute(text("select 1")).scalar_one()

    assert result == 1


def test_database_engine_uses_configured_database_url() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    assert str(engine.url) == "sqlite+pysqlite:///:memory:"
