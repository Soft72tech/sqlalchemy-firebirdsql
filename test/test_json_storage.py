import json

import pytest
from sqlalchemy import JSON, Column, MetaData, Table, create_engine, insert, select
from sqlalchemy.dialects import registry
from sqlalchemy.schema import CreateTable
from sqlalchemy.pool import NullPool


@pytest.fixture(params=["firebird+firebirdsql", "firebird+firebirdsql_async"])
def dialect(request):
    name = request.param
    module = "sqlalchemy_firebirdsql.firebirdsql"
    cls = "FirebirdDialect_firebirdsql" if name == "firebird+firebirdsql" else "FirebirdDialectAsync_firebirdsql"
    registry.register(name.replace("+", "."), module, cls)
    engine = create_engine(name + "://", json_serializer=lambda value: json.dumps(value, sort_keys=True),
                           json_deserializer=json.loads, poolclass=NullPool)
    try:
        yield engine.dialect
    finally:
        engine.dispose()


def test_json_storage_processors_and_compilation(dialect):
    table = Table("payload", MetaData(), Column("data", JSON))
    compiled = str(insert(table).values(data={"answer": 42}).compile(dialect=dialect))
    assert "INSERT INTO payload" in compiled
    assert "data BLOB" in str(CreateTable(table).compile(dialect=dialect))
    typ = dialect.type_descriptor(JSON())
    bind = typ.bind_processor(dialect)
    result = typ.result_processor(dialect, None)
    encoded = bind({"answer": 42})
    assert encoded == '{"answer": 42}'
    assert result(encoded) == {"answer": 42}
    assert bind(None) == "null"
    assert bind(JSON.NULL) == "null"
    assert dialect.type_descriptor(JSON(none_as_null=True)).bind_processor(dialect)(None) is None
    assert result(None) is None


def test_json_default_processors():
    from sqlalchemy_firebirdsql.types import FirebirdJSON
    from sqlalchemy_firebirdsql.base import FirebirdDialect

    typ = FirebirdJSON()
    dialect = FirebirdDialect()
    assert typ.result_processor(dialect, None)('{"x": 1}') == {"x": 1}
    assert typ.bind_processor(dialect)({"x": 1}) == '{"x": 1}'
