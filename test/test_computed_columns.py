import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import Column, Computed, Integer, MetaData, Table, create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import CompileError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateTable

from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialectAsync_firebirdsql,
    FirebirdDialect_firebirdsql,
)


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql,
                                        FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('persisted', [None, False, True])
def test_computed_persistence_ddl(dialect_cls, persisted):
    table = Table('computed_ddl', MetaData(), Column('value', Integer),
                  Column('result', Integer, Computed('value + 2', persisted=persisted)))
    if persisted is True:
        with pytest.raises(CompileError, match='persisted=True'):
            CreateTable(table).compile(dialect=dialect_cls())
    else:
        sql = str(CreateTable(table).compile(dialect=dialect_cls()))
        assert 'GENERATED ALWAYS AS (value + 2)' in sql
        assert 'STORED' not in sql and 'VIRTUAL' not in sql


def check_live(conn):
    table = Table('computed_' + uuid4().hex[:12], MetaData(),
                  Column('normal', Integer),
                  Column('default_result', Integer, Computed('normal + 42')),
                  Column('virtual_result', Integer, Computed('normal + 2', persisted=False)))
    table.create(conn)
    conn.commit()
    try:
        reflected = Table(table.name, MetaData(), autoload_with=conn)
        assert reflected.c.default_result.computed.persisted is False
        assert reflected.c.virtual_result.computed.persisted is False
        assert reflected.c.normal.computed is None
        cols = {col['name']: col for col in inspect(conn).get_columns(table.name)}
        for name in ('default_result', 'virtual_result'):
            assert cols[name]['computed']['persisted'] is False
            assert cols[name]['default'] is None
        conn.execute(table.insert().values(normal=1))
        assert conn.execute(select(table)).one() == (1, 43, 3)
        conn.execute(table.update().values(normal=5))
        assert conn.execute(select(table)).one() == (5, 47, 7)
        conn.commit()
    finally:
        conn.rollback()
        table.drop(conn)
        conn.commit()


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'),
                    reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
def test_live_virtual_computed_reflection_and_updates(async_):
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async' if async_ else 'firebird+firebirdsql')
    if async_:
        async def run():
            engine = create_async_engine(url)
            try:
                async with engine.connect() as conn:
                    await conn.run_sync(check_live)
            finally:
                await engine.dispose()
        asyncio.run(run())
    else:
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                check_live(conn)
        finally:
            engine.dispose()
