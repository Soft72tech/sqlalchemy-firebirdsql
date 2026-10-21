import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.util.concurrency import greenlet_spawn
from firebirdsql.aio.fbcore import AsyncConnection
from firebirdsql.err import OperationalError
from sqlalchemy_firebirdsql.firebirdsql import AsyncAdapt_firebirdsql_connection


def raw_connection():
    raw = object.__new__(AsyncConnection)
    raw.sock = SimpleNamespace(close=Mock(), async_recv=AsyncMock())
    raw.db_handle = 1
    raw._transaction = None
    raw._cursors = {}
    raw.timeout = None
    raw.is_services = False
    raw._op_detach = Mock()
    raw._async_op_response = AsyncMock(return_value=(0, None, b''))
    return raw


def test_aclose_rolls_back_and_detaches():
    raw = raw_connection()
    sock = raw.sock
    transaction = SimpleNamespace(rollback=AsyncMock())
    raw._cursors = {Mock(rollback=transaction.rollback): []}
    asyncio.run(raw.aclose())
    transaction.rollback.assert_awaited_once()
    raw._op_detach.assert_called_once()
    raw._async_op_response.assert_awaited_once()
    sock.close.assert_called_once()
    assert raw.sock is None
    asyncio.run(raw.aclose())


@pytest.mark.parametrize('failure', [OperationalError('offline'), asyncio.CancelledError()])
def test_aclose_failure_always_discards_transport(failure):
    raw = raw_connection()
    sock = raw.sock
    raw._async_op_response.side_effect = failure
    with pytest.raises(type(failure)):
        asyncio.run(raw.aclose())
    sock.close.assert_called_once()
    assert raw.is_disconnect()


def test_adapter_close_awaits_and_terminate_does_not_wait():
    raw = SimpleNamespace(aclose=AsyncMock(), terminate=Mock())
    adapter = object.__new__(AsyncAdapt_firebirdsql_connection)
    adapter._connection = raw
    asyncio.run(greenlet_spawn(adapter.close))
    raw.aclose.assert_awaited_once()
    adapter.terminate()
    raw.terminate.assert_called_once()


@pytest.mark.parametrize('mode', ['cancel', 'timeout', 'eof', 'oserror'])
def test_receive_failure_discards_protocol_state(mode):
    async def run():
        raw = raw_connection()
        sock = raw.sock
        started = asyncio.Event()

        async def receive(n):
            started.set()
            if mode == 'eof':
                return b''
            if mode == 'oserror':
                raise ConnectionResetError('reset')
            await asyncio.Event().wait()

        sock.async_recv.side_effect = receive
        if mode == 'timeout':
            raw.timeout = 0.01
        task = asyncio.create_task(raw._async_recv_channel(4))
        await started.wait()
        if mode == 'cancel':
            task.cancel()
        with pytest.raises(asyncio.CancelledError if mode == 'cancel' else OperationalError):
            await task
        assert raw.is_disconnect()
        sock.close.assert_called_once()
    asyncio.run(run())


def test_ping_reconnect_retries_ping_not_reconnect():
    raw = raw_connection()
    raw._op_ping = Mock()
    raw._async_op_response.side_effect = [OperationalError('offline'), (0, None, b'')]
    raw.reconnect = AsyncMock()
    assert asyncio.run(raw.ping()) is True
    raw.reconnect.assert_awaited_once()
    assert raw._op_ping.call_count == 2


def test_ping_without_reconnect_preserves_error():
    raw = raw_connection()
    raw._op_ping = Mock(side_effect=OperationalError('offline'))
    with pytest.raises(OperationalError, match='offline'):
        asyncio.run(raw.ping(reconnect=False))
    raw.terminate()


def test_context_exit_cleans_up_even_if_commit_fails():
    raw = raw_connection()
    raw.commit = AsyncMock(side_effect=OperationalError('commit failed'))
    with pytest.raises(OperationalError, match='commit failed'):
        asyncio.run(raw.__aexit__(None, None, None))
    assert raw.is_disconnect()


def test_socket_receive_yields_to_event_loop():
    import socket
    from firebirdsql.aio.stream import AsyncSocketStream

    async def run():
        reader, writer = socket.socketpair()
        stream = object.__new__(AsyncSocketStream)
        reader.setblocking(False)
        stream._sock = reader
        stream.loop = asyncio.get_running_loop()
        stream.read_translator = None
        stream._last_send_task = None
        stream._decompressor = None
        stream._buf = b''
        try:
            task = asyncio.create_task(stream.async_recv(1))
            await asyncio.sleep(0.01)
            assert not task.done()
            writer.send(b'x')
            assert await asyncio.wait_for(task, 1) == b'x'
            assert not reader.getblocking()
        finally:
            reader.close()
            writer.close()
    asyncio.run(run())


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='isolated DB required')
def test_live_dispose_cancel_disconnect_and_pool_recovery(monkeypatch):
    async def run():
        url = make_url(os.environ['FIREBIRD_TEST_URL']).set(drivername='firebird+firebirdsql_async')
        engine = create_async_engine(url, pool_size=1, max_overflow=0)
        try:
            async with engine.connect() as conn:
                raw = (await conn.get_raw_connection()).driver_connection
                def forbidden(*args, **kw):
                    raise AssertionError('sync response read')
                monkeypatch.setattr(raw, '_op_response', forbidden)
                assert (await conn.execute(text('SELECT 1 FROM rdb$database'))).scalar_one() == 1
            await engine.dispose()
            assert raw.is_disconnect()
            # Deterministically cancel while awaiting a real query response.
            async with engine.connect() as conn:
                raw = (await conn.get_raw_connection()).driver_connection
                started = asyncio.Event()
                async def stalled_receive(n):
                    started.set()
                    await asyncio.Event().wait()
                monkeypatch.setattr(raw.sock, 'async_recv', stalled_receive)
                task = asyncio.create_task(conn.execute(text('SELECT 1 FROM rdb$database')))
                await started.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert raw.is_disconnect()
                assert conn.invalidated
            async with engine.connect() as conn:
                assert (await conn.execute(text('SELECT 2 FROM rdb$database'))).scalar_one() == 2
                raw = (await conn.get_raw_connection()).driver_connection
                raw.sock._sock.shutdown(2)
                with pytest.raises(Exception) as error:
                    await conn.execute(text('SELECT 3 FROM rdb$database'))
                assert error.value.connection_invalidated
            async with engine.connect() as conn:
                assert (await conn.execute(text('SELECT 4 FROM rdb$database'))).scalar_one() == 4
        finally:
            await engine.dispose()
    asyncio.run(run())
