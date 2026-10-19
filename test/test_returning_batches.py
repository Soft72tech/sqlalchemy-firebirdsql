import asyncio
import os

import pytest
from sqlalchemy import Column, Identity, Integer, LargeBinary, MetaData, Table, Text, create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
def test_returning_uses_row_fallback_not_multivalues(dialect_cls):
    dialect = dialect_cls()
    assert dialect.use_insertmanyvalues
    assert dialect.insert_executemany_returning
    assert dialect.insert_executemany_returning_sort_by_parameter_order
    assert not dialect.supports_multivalues_insert


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
@pytest.mark.parametrize('ordered', [False, True])
def test_live_returning_rows_blobs_defaults_and_rollback(async_, ordered):
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(drivername='firebird+firebirdsql')
    setup = create_engine(url)
    table = Table('returning_batch_regression', MetaData(),
                  Column('id', Integer, Identity(), primary_key=True),
                  Column('payload', LargeBinary), Column('body', Text))
    data = [{'payload': b'\x00\xff', 'body': 'текст'},
            {'payload': None, 'body': None},
            {'payload': b'z' * 20000, 'body': ''}]
    statement = table.insert().returning(table.c.id, table.c.payload, table.c.body,
                                         sort_by_parameter_order=ordered)
    statements = []

    def record(connection, cursor, sql, parameters, context, executemany):
        if sql.lstrip().upper().startswith('INSERT'):
            statements.append(sql)

    def check(rows):
        assert [tuple(row)[1:] for row in rows] == [(row['payload'], row['body']) for row in data]
        assert len({row[0] for row in rows}) == len(data)

    created = False
    try:
        with setup.begin() as connection:
            table.create(connection)
        created = True
        if async_:
            async def run():
                engine = create_async_engine(url.set(drivername='firebird+firebirdsql_async'))
                event.listen(engine.sync_engine, 'before_cursor_execute', record)
                try:
                    async with engine.connect() as connection:
                        check((await connection.execute(statement, data)).all())
                        result = await connection.execute(table.insert().return_defaults(), data)
                        assert len(result.inserted_primary_key_rows) == 3
                        assert all(row[0] is not None for row in result.inserted_primary_key_rows)
                        await connection.rollback()
                        assert await connection.scalar(select(func.count()).select_from(table)) == 0
                finally:
                    await engine.dispose()
            asyncio.run(run())
        else:
            event.listen(setup, 'before_cursor_execute', record)
            with setup.connect() as connection:
                check(connection.execute(statement, data).all())
                result = connection.execute(table.insert().return_defaults(), data)
                assert len(result.inserted_primary_key_rows) == 3
                assert all(row[0] is not None for row in result.inserted_primary_key_rows)
                connection.rollback()
                assert connection.scalar(select(func.count()).select_from(table)) == 0
        assert len(statements) == 6  # One INSERT per input row, not native bulk SQL.
    finally:
        if created:
            with setup.begin() as connection:
                table.drop(connection)
        setup.dispose()
