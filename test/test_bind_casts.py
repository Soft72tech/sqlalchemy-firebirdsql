from sqlalchemy import BigInteger, Integer, column, exists, literal, select, table
import pytest

from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialect_firebirdsql,
    FirebirdDialectAsync_firebirdsql,
)


def test_integer_projection_bind_cast():
    stuff = table("stuff", column("data"))
    statement = select(literal(1, Integer)).where(
        exists(select(stuff).where(stuff.c.data == "some data"))
    )
    for dialect in (FirebirdDialect_firebirdsql(paramstyle="qmark"), FirebirdDialectAsync_firebirdsql(paramstyle="qmark")):
        compiled = str(statement.compile(dialect=dialect))
        assert "SELECT CAST(? AS INTEGER) AS anon_1" in compiled
        assert "WHERE EXISTS" in compiled


@pytest.mark.parametrize("value", [-(2**63), -2147483649, -2147483648, 2147483648, 2**63 - 1])
@pytest.mark.parametrize("type_", [None, BigInteger, BigInteger()])
def test_bigint_comparison_bind_cast(value, type_):
    statement = select(value).where(literal(value, type_=type_) == value)
    for dialect in (FirebirdDialect_firebirdsql(paramstyle="qmark"), FirebirdDialectAsync_firebirdsql(paramstyle="qmark")):
        compiled = str(statement.compile(dialect=dialect))
        assert "WHERE CAST(? AS BIGINT) = CAST(? AS BIGINT)" in compiled
