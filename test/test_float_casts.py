import pytest
from sqlalchemy import Float, Double, REAL, literal, select
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('type_,expected', [(Float(), 'DOUBLE PRECISION'), (Float(24), 'FLOAT(24)'), (Float(53), 'FLOAT(53)'), (Double(), 'DOUBLE PRECISION')])
def test_float_bind_precision(dialect_cls, type_, expected):
    dialect = dialect_cls(paramstyle='qmark')
    assert dialect.type_compiler_instance.process(type_) == expected
    sql = str(select(literal(2.4, type_)).compile(dialect=dialect))
    assert f'CAST(? AS {expected})' in sql
    assert dialect.type_compiler_instance.process(REAL()) == 'REAL'
