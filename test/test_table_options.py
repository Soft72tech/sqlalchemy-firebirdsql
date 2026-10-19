import asyncio
import os
from unittest.mock import Mock

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('relation_type,expected', [
    (0, {}), (1, {}), (4, {'firebird_on_commit': 'PRESERVE ROWS'}),
    (5, {'firebird_on_commit': 'DELETE ROWS'}),
])
def test_table_options_use_relation_type_and_bound_name(dialect_cls, relation_type, expected):
    connection = Mock()
    connection.exec_driver_sql.return_value.first.return_value = (relation_type,)
    assert dialect_cls().get_table_options(connection, 'sample') == expected
    assert connection.exec_driver_sql.call_args.args[1] == ('SAMPLE',)


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
def test_missing_table_options_raise(dialect_cls):
    connection = Mock()
    connection.exec_driver_sql.return_value.first.return_value = None
    with pytest.raises(NoSuchTableError):
        dialect_cls().get_table_options(connection, 'missing')


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
def test_live_persistent_and_gtt_options(async_):
    from sqlalchemy.engine.reflection import ObjectKind, ObjectScope
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(drivername='firebird+firebirdsql')
    metadata = MetaData()
    persistent = Table('OptionsCase', metadata, Column('id', Integer), quote=True)
    preserve = Table('options_preserve_regression', metadata, Column('id', Integer),
                     prefixes=['GLOBAL TEMPORARY'], firebird_on_commit='PRESERVE ROWS')
    delete = Table('options_delete_regression', metadata, Column('id', Integer),
                   prefixes=['GLOBAL TEMPORARY'], firebird_on_commit='DELETE ROWS')
    expected = {(None, persistent.name): {},
                (None, preserve.name): {'firebird_on_commit': 'PRESERVE ROWS'},
                (None, delete.name): {'firebird_on_commit': 'DELETE ROWS'}}

    def check(connection):
        inspector = inspect(connection)
        for (_, name), options in expected.items():
            assert inspector.get_table_options(name) == options
        assert inspector.get_multi_table_options(
            filter_names=[key[1] for key in expected], scope=ObjectScope.ANY,
            kind=ObjectKind.TABLE) == expected
        with pytest.raises(NoSuchTableError):
            inspector.get_table_options('missing_options_regression')

    if async_:
        async def run():
            engine = create_async_engine(url.set(drivername='firebird+firebirdsql_async'))
            created = False
            try:
                async with engine.begin() as connection:
                    await connection.run_sync(metadata.create_all)
                created = True
                async with engine.connect() as connection:
                    await connection.run_sync(check)
            finally:
                if created:
                    async with engine.begin() as connection:
                        await connection.run_sync(metadata.drop_all)
                await engine.dispose()
        asyncio.run(run())
    else:
        engine = create_engine(url)
        created = False
        try:
            with engine.begin() as connection:
                metadata.create_all(connection)
            created = True
            with engine.connect() as connection:
                check(connection)
        finally:
            if created:
                with engine.begin() as connection:
                    metadata.drop_all(connection)
            engine.dispose()
