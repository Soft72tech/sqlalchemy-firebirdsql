import pytest
from sqlalchemy import String, VARCHAR, column, literal, select
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('type_', [String(), String(1), VARCHAR(1)])
def test_string_bind_does_not_truncate_pattern(dialect_cls, type_):
    dialect = dialect_cls(paramstyle='qmark')
    sql = str(select(column('value', type_)).where(column('value', type_).like('%long pattern%')).compile(dialect=dialect))
    assert 'LIKE CAST(? AS BLOB SUB_TYPE TEXT)' in sql
    sql = str(select(literal('a', type_) + literal('b', type_)).compile(dialect=dialect))
    assert sql.count('CAST(? AS BLOB SUB_TYPE TEXT)') == 2
