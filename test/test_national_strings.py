import asyncio
import os

import pytest
from sqlalchemy import Column, Integer, MetaData, NCHAR, NVARCHAR, Table, create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('length,expected', [(52, 52), (None, 255)])
def test_nvarchar_uses_supported_national_varying_syntax(dialect_cls, length, expected):
    dialect = dialect_cls()
    assert dialect.type_compiler_instance.process(NVARCHAR(length)) == f'NATIONAL CHARACTER VARYING({expected})'


def test_nvarchar_keeps_collation():
    dialect = FirebirdDialect_firebirdsql()
    assert dialect.type_compiler_instance.process(NVARCHAR(52, collation='ISO8859_1')) == 'NATIONAL CHARACTER VARYING(52) COLLATE "ISO8859_1"'


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
def test_live_national_strings_reflect_charset_and_round_trip(async_):
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(drivername='firebird+firebirdsql')
    engine = create_engine(url)
    table = Table('national_string_regression', MetaData(),
                  Column('id', Integer, primary_key=True, autoincrement=False),
                  Column('varying_value', NVARCHAR(52)), Column('fixed_value', NCHAR(52)))
    created = False
    try:
        with engine.begin() as connection:
            table.create(connection)
        created = True
        with engine.connect() as connection:
            columns = {item['name']: item['type'] for item in inspect(connection).get_columns(table.name)}
            for name in ('varying_value', 'fixed_value'):
                assert columns[name].length == 52
                assert columns[name].charset == 'ISO8859_1'
        values = {'id': 1, 'varying_value': 'café', 'fixed_value': 'olé'}
        if async_:
            async def run():
                async_engine = create_async_engine(url.set(drivername='firebird+firebirdsql_async'))
                try:
                    async with async_engine.begin() as connection:
                        await connection.execute(table.insert(), values)
                        row = (await connection.execute(select(table))).one()
                        assert tuple(row) == (1, 'café', 'olé')
                finally:
                    await async_engine.dispose()
            asyncio.run(run())
        else:
            with engine.begin() as connection:
                connection.execute(table.insert(), values)
                assert tuple(connection.execute(select(table)).one()) == (1, 'café', 'olé')
    finally:
        if created:
            with engine.begin() as connection:
                table.drop(connection)
        engine.dispose()
