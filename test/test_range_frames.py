import asyncio
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Date, DateTime, Integer, Interval, Time, bindparam, column, func, literal, select, union_all
from sqlalchemy.sql import elements
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql
from sqlalchemy_firebirdsql.types import _FirebirdRangeOffset

if not hasattr(elements, 'FrameClause'):
    pytest.skip('Typed RANGE frames require SQLAlchemy 2.1', allow_module_level=True)


def window(order):
    return func.sum(literal(1)).over(
        order_by=order,
        range_=elements.FrameClause(bindparam('offset', type_=Interval()), None,
                                   elements.FrameClauseType.PRECEDING,
                                   elements.FrameClauseType.CURRENT))


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('type_', [Date(), DateTime(), Time()])
@pytest.mark.parametrize('descending', [False, True])
def test_temporal_range_compiles_numeric_without_mutating_input(dialect_cls, type_, descending):
    ordered = column('ordered', type_)
    statement = select(window(ordered.desc() if descending else ordered))
    original = statement._generate_cache_key()
    sql = str(statement.compile(dialect=dialect_cls(paramstyle='qmark')))
    assert 'RANGE BETWEEN CAST(? AS NUMERIC(38, 18)) PRECEDING' in sql
    assert statement._generate_cache_key() == original
    assert isinstance(statement.selected_columns[0].range_.lower_bind.type, Interval)


@pytest.mark.parametrize('unit,value,expected', [
    ('date', timedelta(days=7), Decimal(7)),
    ('timestamp', timedelta(hours=12), Decimal('0.5')),
    ('time', timedelta(seconds=2, microseconds=100), Decimal('2.0001')),
])
def test_range_offset_units(unit, value, expected):
    assert _FirebirdRangeOffset(unit).process_bind_param(value, None) == expected


@pytest.mark.parametrize('unit,value', [('date', timedelta(hours=12)),
                                      ('time', timedelta(seconds=-1))])
def test_invalid_offsets_fail_instead_of_rounding(unit, value):
    with pytest.raises(ValueError):
        _FirebirdRangeOffset(unit).process_bind_param(value, None)


def test_timedelta_requires_temporal_ordering():
    from sqlalchemy.exc import CompileError
    with pytest.raises(CompileError, match='timedelta RANGE'):
        select(window(column('number', Integer))).compile(dialect=FirebirdDialect_firebirdsql())


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='Set isolated FIREBIRD_TEST_URL')
@pytest.mark.parametrize('async_', [False, True])
@pytest.mark.parametrize('type_,values,large,small', [
    (Date(), [date(2025, 1, day) for day in (1, 3, 6)], timedelta(days=3), timedelta(days=1)),
    (DateTime(), [datetime(2025, 1, 1, 12, minute) for minute in (0, 2, 5)], timedelta(minutes=3), timedelta(minutes=1)),
    (Time(), [time(12, minute) for minute in (0, 2, 5)], timedelta(minutes=3), timedelta(minutes=1)),
])
def test_live_temporal_ranges_rebind_cached_offsets(async_, type_, values, large, small):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    url = make_url(os.environ['FIREBIRD_TEST_URL']).set(
        drivername='firebird+firebirdsql_async' if async_ else 'firebird+firebirdsql')
    data = union_all(*(select(literal(index, Integer).label('value'),
                              literal(value, type_).label('ordered'))
                       for index, value in enumerate(values, 1))).subquery()
    statement = select(func.sum(data.c.value).over(
        order_by=data.c.ordered,
        range_=elements.FrameClause(bindparam('offset', type_=Interval()), None,
                                   elements.FrameClauseType.PRECEDING,
                                   elements.FrameClauseType.CURRENT))).order_by(data.c.ordered)
    if async_:
        async def run():
            engine = create_async_engine(url)
            try:
                async with engine.connect() as connection:
                    for offset, expected in [(large, [1, 3, 5]), (small, [1, 2, 3])]:
                        result = await connection.execute(statement, {'offset': offset})
                        assert result.scalars().all() == expected
            finally:
                await engine.dispose()
        asyncio.run(run())
    else:
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                for offset, expected in [(large, [1, 3, 5]), (small, [1, 2, 3])]:
                    assert connection.execute(statement, {'offset': offset}).scalars().all() == expected
        finally:
            engine.dispose()
