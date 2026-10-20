import asyncio
import os

import pytest
from sqlalchemy import Boolean, Integer, and_, cast, create_engine, literal, not_, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from sqlalchemy_firebirdsql.requirements import Requirements
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='isolated DB required')
@pytest.mark.parametrize('async_', [False, True])
def test_boolean_predicates_in_select_list(async_):
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async' if async_ else 'firebird+firebirdsql')

    def check(conn):
        unknown = cast(literal(None), Integer) == 1
        expressions = (
            literal(2) > 1, literal(2) < 1,
            and_(literal(2) > 1, literal(3) < 4),
            not_(literal(2) > 1), unknown,
            literal(True, Boolean), literal(False, Boolean),
            literal(None, Boolean),
        )
        row = conn.execute(select(*expressions)).one()
        assert tuple(row) == (True, False, True, False, None, True, False, None)
        assert all(value is None or type(value) is bool for value in row)

    if async_:
        async def run():
            engine = create_async_engine(url)
            try:
                async with engine.connect() as conn:
                    await conn.run_sync(check)
            finally:
                await engine.dispose()
        asyncio.run(run())
    else:
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                check(conn)
        finally:
            engine.dispose()


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('value', [True, False, None])
def test_boolean_projection_bind_is_typed(dialect_cls, value):
    sql = str(select(literal(value, Boolean)).compile(dialect=dialect_cls(paramstyle='qmark')))
    assert 'CAST(? AS BOOLEAN)' in sql


@pytest.mark.parametrize('gate', [
    'boolean_col_expressions', 'date_historic', 'datetime_historic',
    'percent_schema_names',
])
def test_verified_native_requirements_are_open(gate):
    assert getattr(Requirements(), gate).enabled
