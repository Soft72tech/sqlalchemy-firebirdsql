import asyncio
import os
from uuid import uuid4
from collections import deque
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from sqlalchemy_firebirdsql.firebirdsql import AsyncAdapt_firebirdsql_cursor


class RawCursor:
    description = None

    def __init__(self, count):
        self.execute = AsyncMock()
        self.executemany = AsyncMock()
        self.fetchall = AsyncMock(return_value=[(1,), (2,)])
        self.get_rowcount = AsyncMock(return_value=count)

    @property
    def rowcount(self):
        raise AssertionError('synchronous driver rowcount accessed')


def make_adapter(raw):
    adapter = object.__new__(AsyncAdapt_firebirdsql_cursor)
    adapter._cursor = raw
    adapter._rowcount = -1
    adapter._rows = deque()
    adapter._adapt_connection = SimpleNamespace(_execute_mutex=asyncio.Lock())
    return adapter


@pytest.mark.parametrize('many', [False, True])
@pytest.mark.parametrize('count', [-1, 0, 3])
def test_async_adapter_caches_rowcount_without_sync_io(many, count):
    raw = RawCursor(count)
    adapter = make_adapter(raw)
    async def run():
        if many:
            await adapter._executemany_async('query', [(1,), (2,)])
        else:
            await adapter._execute_async('query', (1,))
        if many:
            raw.get_rowcount.assert_not_awaited()
        else:
            raw.get_rowcount.assert_awaited_once()
    asyncio.run(run())
    # Deliberately outside any greenlet or event loop, also after raw disposal.
    adapter._cursor = None
    assert adapter.rowcount == (-1 if many else count)
    assert adapter.rowcount == (-1 if many else count)


def test_async_adapter_fetches_before_count_and_resets_on_error():
    raw = RawCursor(2)
    raw.description = [('value',)]
    adapter = make_adapter(raw)
    async def get_count():
        assert list(adapter._rows) == [(1,), (2,)]
        assert adapter._adapt_connection._execute_mutex.locked()
        return 2
    raw.get_rowcount.side_effect = get_count
    async def run():
        await adapter._execute_async('query', None)
        assert adapter.rowcount == 2
        raw.execute.side_effect = RuntimeError('offline')
        with pytest.raises(RuntimeError, match='offline'):
            await adapter._execute_async('query', None)
        assert adapter.rowcount == -1
    asyncio.run(run())


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'),
                    reason='Set isolated FIREBIRD_TEST_URL')
def test_live_async_rowcount_never_uses_sync_response(monkeypatch):
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async')
    table = 'rc_' + uuid4().hex[:12]

    def forbidden(*args, **kwargs):
        raise AssertionError('synchronous response read on async connection')

    async def run():
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text(f'CREATE TABLE {table} (id INTEGER)'))
                await conn.commit()
                try:
                    raw = (await conn.get_raw_connection()).dbapi_connection._connection
                    with monkeypatch.context() as patch:
                        patch.setattr(raw, '_op_response', forbidden)
                        for value in range(3):
                            result = await conn.execute(
                                text(f'INSERT INTO {table} VALUES (:value)'),
                                {'value': value},
                                execution_options={'preserve_rowcount': True})
                            result.close()
                            assert result.rowcount == 1
                        result = await conn.execute(text(f'UPDATE {table} SET id = id + 1'))
                        result.close()
                        assert result.rowcount == 3
                        result = await conn.execute(text(f'UPDATE {table} SET id = 0 WHERE id = 99'))
                        assert result.rowcount == 0
                        result = await conn.execute(text(f'SELECT id FROM {table}'),
                                                    execution_options={'preserve_rowcount': True})
                        assert len(result.all()) == 3
                        assert result.rowcount == 3
                        result = await conn.execute(text(f'DELETE FROM {table}'))
                        assert result.rowcount == 3
                        # Rollback must leave the connection usable as well.
                        await conn.rollback()
                        assert (await conn.execute(text(f'SELECT COUNT(*) FROM {table}'))).scalar_one() == 0
                finally:
                    await conn.rollback()
                    await conn.execute(text(f'DROP TABLE {table}'))
                    await conn.commit()
        finally:
            await engine.dispose()
    asyncio.run(run())
