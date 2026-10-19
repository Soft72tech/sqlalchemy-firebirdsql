import asyncio
import os

import pytest
from sqlalchemy import BigInteger, literal, select
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('method,function', [
    ('bitwise_or', 'BIN_OR'), ('bitwise_and', 'BIN_AND'),
    ('bitwise_xor', 'BIN_XOR'), ('bitwise_lshift', 'BIN_SHL'),
    ('bitwise_rshift', 'BIN_SHR'), ('bitwise_not', 'BIN_NOT'),
])
def test_bitwise_compiles_native_functions(dialect_cls, method, function):
    left = literal(5, BigInteger)
    expression = getattr(left, method)(*(() if method == 'bitwise_not' else (literal(2, BigInteger),)))
    sql = str(select(expression).compile(dialect=dialect_cls(paramstyle='qmark')))
    assert f'{function}(CAST(? AS BIGINT)' in sql
    assert sql.count('CAST(? AS BIGINT)') == (1 if method == 'bitwise_not' else 2)


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
@pytest.mark.parametrize('value,shift', [(5, 1), (-5, 2), (2**40 + 1, 3), (None, 1)])
def test_live_bitwise_signed_bigint_and_null(async_, value, shift):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    left, right = literal(value, BigInteger), literal(shift, BigInteger)
    statement = select(left.bitwise_or(right), left.bitwise_and(right),
                       left.bitwise_xor(right), left.bitwise_lshift(right),
                       left.bitwise_rshift(right), left.bitwise_not())
    expected = ((None,) * 6 if value is None else
                (value | shift, value & shift, value ^ shift,
                 value << shift, value >> shift, ~value))
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async' if async_ else 'firebird+firebirdsql')
    if async_:
        async def run():
            engine = create_async_engine(url)
            try:
                async with engine.connect() as connection:
                    assert tuple((await connection.execute(statement)).one()) == expected
            finally:
                await engine.dispose()
        asyncio.run(run())
    else:
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                assert tuple(connection.execute(statement).one()) == expected
        finally:
            engine.dispose()
