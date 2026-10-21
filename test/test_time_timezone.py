"""Focused TIME timezone coverage; live checks require an explicit baseline URL.

Fixed-offset encoding and named-zone reference dates belong to the DBAPI driver.
Keep the general requirement closed until those paths have live evidence.
"""
import asyncio
import datetime
import os

import pytest
from sqlalchemy import Time, bindparam, create_engine, literal, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialectAsync_firebirdsql,
    FirebirdDialect_firebirdsql,
)
from sqlalchemy_firebirdsql.requirements import Requirements


@pytest.mark.parametrize('dialect_cls', [
    FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql,
])
@pytest.mark.parametrize('timezone', [False, True])
def test_time_timezone_compilation(dialect_cls, timezone):
    dialect = dialect_cls(paramstyle='qmark')
    type_ = Time(timezone=timezone)
    expected = 'TIME WITH TIME ZONE' if timezone else 'TIME'
    assert dialect.type_compiler.process(type_) == expected
    impl = type_.dialect_impl(dialect)
    assert impl.timezone is timezone
    sql = str(select(literal(None, type_)).compile(dialect=dialect))
    assert f'CAST(? AS {expected})' in sql


def test_time_timezone_requirement_remains_conservative():
    assert not Requirements().time_timezone.enabled


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='isolated DB required')
@pytest.mark.parametrize('async_', [False, True])
def test_time_timezone_utc_roundtrip(async_):
    """UTC only: this does not certify fixed offsets or named-zone DST rules."""
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async' if async_ else 'firebird+firebirdsql')
    # A SELECT-only probe avoids DDL or modification of the existing database.
    values = [
        datetime.time(0, tzinfo=datetime.timezone.utc),
        datetime.time(12, 34, 56, 123400, tzinfo=datetime.timezone.utc),
        datetime.time(23, 59, 59, 999900, tzinfo=datetime.timezone.utc),
        None,
    ]

    def check(conn):
        statement = select(bindparam('value', type_=Time(timezone=True)))
        for value in values:
            # Reuse the statement/cache path with a different value each time.
            result = conn.scalar(statement, {'value': value})
            assert result == value
            if result is not None:
                assert result.utcoffset() == datetime.timedelta(0)

        # Known driver limitation, not a supported timezone roundtrip:
        # encoding looks up str(tzinfo) as a named zone and rejects UTC+05:30.
        offset_value = datetime.time(
            12, 34, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        with pytest.raises(KeyError) as error:
            conn.scalar(statement, {'value': offset_value})
        assert error.value.args == ('UTC+05:30',)
        assert conn.scalar(statement, {'value': values[1]}) == values[1]

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
