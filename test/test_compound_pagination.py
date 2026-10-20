import asyncio
import os

import pytest
from sqlalchemy import Integer, bindparam, create_engine, literal, select, union_all
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialectAsync_firebirdsql,
    FirebirdDialect_firebirdsql,
)


def statement(mode, alias=False):
    data = union_all(*(select(literal(i, Integer).label('value'))
                       for i in range(1, 5))).subquery()
    branch = select(data.c.value).order_by(data.c.value)
    if mode == 'fetch':
        branch = branch.offset(bindparam('offset', type_=Integer())).fetch(1)
    elif mode == 'expression':
        branch = branch.offset(bindparam('offset', type_=Integer())).limit(
            bindparam('size', type_=Integer()) + literal(0))
    else:
        branch = branch.offset(bindparam('offset', type_=Integer()))
    result = union_all(branch, select(literal(9, Integer).label('value')))
    if alias:
        data = result.subquery()
        return select(data.c.value).order_by(data.c.value.desc())
    return result.order_by(result.selected_columns.value.desc())


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql,
                                        FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('mode', ['fetch', 'expression', 'offset'])
def test_compilation_preserves_cache_key_and_bindings(dialect_cls, mode):
    stmt = statement(mode)
    key = stmt._generate_cache_key()
    compiled = stmt.compile(dialect=dialect_cls(paramstyle='qmark'))
    assert 'SELECT * FROM (SELECT' in str(compiled)
    assert 'AS fb_union_branch' in str(compiled)
    assert str(compiled).endswith('ORDER BY 1 DESC')
    assert 'offset' in compiled.params
    assert stmt._generate_cache_key() == key


def test_simple_select_does_not_gain_wrapper():
    sql = str(select(literal(1)).limit(1).compile(
        dialect=FirebirdDialect_firebirdsql()))
    assert 'fb_union_branch' not in sql
    assert 'ROWS 1 TO' in sql


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'),
                    reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('mode', ['fetch', 'expression', 'offset'])
def test_live_cached_compound_pagination(async_, alias, mode):
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async' if async_ else 'firebird+firebirdsql')
    stmt = statement(mode, alias)
    expected = ([9, 2], [9, 3]) if mode != 'offset' else ([9, 4, 3, 2], [9, 4, 3])

    def check(result, values):
        assert list(result.keys()) == ['value']
        assert result.scalars().all() == values

    if async_:
        async def run():
            engine = create_async_engine(url)
            try:
                async with engine.connect() as conn:
                    for offset, values in enumerate(expected, 1):
                        check(await conn.execute(stmt, {'offset': offset, 'size': 1}), values)
            finally:
                await engine.dispose()
        asyncio.run(run())
    else:
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                for offset, values in enumerate(expected, 1):
                    check(conn.execute(stmt, {'offset': offset, 'size': 1}), values)
        finally:
            engine.dispose()
