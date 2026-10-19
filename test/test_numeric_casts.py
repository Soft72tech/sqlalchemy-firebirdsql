from decimal import Decimal

import pytest
from sqlalchemy import DECIMAL, Integer, Numeric, cast, literal, literal_column, select
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('type_,target', [(None, 'DECFLOAT(34)'), (Numeric(), 'DECFLOAT(34)'), (Numeric(scale=12), 'NUMERIC(38, 12)'), (Numeric(38, 20), 'NUMERIC(38, 20)'), (DECIMAL(18, 6), 'DECIMAL(18, 6)')])
def test_decimal_bind_keeps_scale(dialect_cls, type_, target):
    sql = str(select(literal(Decimal('0.000000123456'), type_)).compile(dialect=dialect_cls(paramstyle='qmark')))
    assert f'CAST(? AS {target})' in sql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
def test_true_division_promotes_both_operands(dialect_cls):
    sql = str(select(literal(15, Integer) / 10).compile(dialect=dialect_cls(paramstyle='qmark')))
    assert 'AS DECFLOAT(34)) / CAST(' in sql
    assert sql.count('AS DECFLOAT(34)') == 2


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('value', ['30000000000000000000000000000000000000', '-99999999999999999999999999999999999999', '0.00000000000012345679', '1E37', '+123'])
def test_high_precision_numeric_literal_parses_exact_decimal_text(dialect_cls, value):
    sql = str(cast(literal_column(value), Numeric(38, 0)).compile(dialect=dialect_cls()))
    assert sql == f"CAST('{value}' AS NUMERIC(38, 0))"


@pytest.mark.parametrize('value', ['price + tax', "1; select 'x'", 'null', 'nan', 'infinity'])
def test_non_numeric_sql_is_not_quoted(value):
    sql = str(cast(literal_column(value), Numeric(38, 0)).compile(dialect=FirebirdDialect_firebirdsql()))
    assert sql == f'CAST({value} AS NUMERIC(38, 0))'


def test_regular_precision_cast_is_unchanged():
    sql = str(cast(literal_column('123'), Numeric(18, 0)).compile(dialect=FirebirdDialect_firebirdsql()))
    assert sql == 'CAST(123 AS NUMERIC(18, 0))'
