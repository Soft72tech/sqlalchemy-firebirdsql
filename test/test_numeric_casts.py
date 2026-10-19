from decimal import Decimal

import pytest
from sqlalchemy import DECIMAL, Integer, Numeric, literal, select
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
