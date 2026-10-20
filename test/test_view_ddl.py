import pytest
from sqlalchemy import String, literal, select
from sqlalchemy import schema

from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialectAsync_firebirdsql,
    FirebirdDialect_firebirdsql,
)

if not hasattr(schema, 'CreateView'):
    pytest.skip('CreateView requires SQLAlchemy 2.1', allow_module_level=True)


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql,
                                        FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('replace', [False, True])
def test_create_view_uses_native_alter_without_mutating_statement(dialect_cls, replace):
    stmt = schema.CreateView(
        select(literal('CREATE OR REPLACE', String).label('message')),
        'Quoted View', or_replace=replace)
    sql = str(stmt.compile(dialect=dialect_cls()))
    prefix = 'CREATE OR ALTER VIEW' if replace else 'CREATE VIEW'
    assert sql.startswith(prefix + ' "Quoted View" AS SELECT')
    assert "'CREATE OR REPLACE'" in sql
    assert 'CAST(' not in sql  # literal SELECT stays literal, no bound params
    assert stmt.or_replace is replace
