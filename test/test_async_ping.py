import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.util.concurrency import greenlet_spawn

from sqlalchemy_firebirdsql.firebirdsql import (
    AsyncAdapt_firebirdsql_connection,
    FirebirdDialectAsync_firebirdsql,
    FirebirdDialect_firebirdsql,
)


@pytest.mark.parametrize("result", [True, False])
def test_ping_awaits_driver_without_reconnect(result):
    raw = SimpleNamespace(ping=AsyncMock(return_value=result))
    adapter = object.__new__(AsyncAdapt_firebirdsql_connection)
    adapter._connection = raw
    assert asyncio.run(greenlet_spawn(adapter.ping)) is result
    raw.ping.assert_awaited_once_with(reconnect=False)


@pytest.mark.parametrize('async_', [False, True])
def test_driver_connection_exposes_original_driver_object(async_):
    raw = object()
    connection = SimpleNamespace(_connection=raw) if async_ else raw
    dialect = (FirebirdDialectAsync_firebirdsql() if async_
               else FirebirdDialect_firebirdsql())
    assert dialect.get_driver_connection(connection) is raw


def test_ping_propagates_driver_errors():
    raw = SimpleNamespace(ping=AsyncMock(side_effect=RuntimeError("offline")))
    adapter = object.__new__(AsyncAdapt_firebirdsql_connection)
    adapter._connection = raw
    with pytest.raises(RuntimeError, match="offline"):
        asyncio.run(greenlet_spawn(adapter.ping))
