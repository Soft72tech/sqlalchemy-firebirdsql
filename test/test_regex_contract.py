"""Keep SQL SIMILAR TO distinct from SQLAlchemy's regexp operators."""
import asyncio
import os

import pytest
from sqlalchemy import String, create_engine, literal, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import CompileError
from sqlalchemy.ext.asyncio import create_async_engine

from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialectAsync_firebirdsql,
    FirebirdDialect_firebirdsql,
)


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql,
                                        FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('operation', ['match', 'replace'])
def test_regexp_is_explicitly_unsupported(dialect_cls, operation):
    value = literal('abc', String)
    expression = (value.regexp_match('b') if operation == 'match'
                  else value.regexp_replace('b', 'x'))
    with pytest.raises(CompileError, match='regular expression'):
        select(expression).compile(dialect=dialect_cls())


def check_similar_to(conn):
    # Full-string matching and SQL wildcards are not a PCRE/search contract.
    cases = [('abc', 'b', False), ('abc', '%b%', True),
             ('abc', 'a_c', True), ('a.c', 'a.c', True),
             ('abc', 'a.c', False), (None, '%', None)]
    statement = text('SELECT CAST(:value AS VARCHAR(20)) SIMILAR TO '
                     'CAST(:pattern AS VARCHAR(20)) FROM RDB$DATABASE')
    for value, pattern, expected in cases:
        assert conn.execute(statement, dict(value=value, pattern=pattern)).scalar_one() is expected


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'),
                    reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
def test_native_similar_to_semantics(async_):
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async' if async_ else 'firebird+firebirdsql')
    if async_:
        async def run():
            engine = create_async_engine(url)
            try:
                async with engine.connect() as conn:
                    await conn.run_sync(check_similar_to)
            finally:
                await engine.dispose()
        asyncio.run(run())
    else:
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                check_similar_to(conn)
        finally:
            engine.dispose()
