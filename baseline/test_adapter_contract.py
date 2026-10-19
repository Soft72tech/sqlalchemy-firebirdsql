"""Offline regressions for identifier quoting and async DBAPI Binary."""
import importlib

from sqlalchemy import Boolean, Column, Integer, MetaData, Table
from sqlalchemy.schema import CreateTable

from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialect_firebirdsql,
    FirebirdDialectAsync_firebirdsql,
)


def test_reserved_value_identifier_is_quoted():
    # Firebird 5 Language Reference, Appendix C: VALUE is reserved.
    table = Table("boolean_table", MetaData(), Column("id", Integer), Column("value", Boolean))
    for dialect_cls in (FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql):
        ddl = str(CreateTable(table).compile(dialect=dialect_cls()))
        assert '"value" BOOLEAN' in ddl
        assert '"id"' not in ddl


def test_async_dbapi_binary_matches_sync():
    sync = importlib.import_module("firebirdsql")
    async_dbapi = FirebirdDialectAsync_firebirdsql.import_dbapi()
    assert async_dbapi.Binary is sync.Binary
    assert async_dbapi.Binary(b"\x00\xffbinary") == sync.Binary(b"\x00\xffbinary")
