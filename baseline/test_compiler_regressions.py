"""Offline regressions for Firebird CAST syntax and UNION ordering."""
import pytest
from sqlalchemy import Date, DateTime, Integer, Time, column, func, select, table, union

from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql
from sqlalchemy_firebirdsql.types import FirebirdDATE


@pytest.mark.parametrize("type_, expected", [
    (DateTime(), "TIMESTAMP"),
    (DateTime(timezone=True), "TIMESTAMP WITH TIME ZONE"),
    (Time(), "TIME"),
    (Time(timezone=True), "TIME WITH TIME ZONE"),
])
def test_temporal_types_preserve_timezone_and_cast_bindings(type_, expected):
    dialect = FirebirdDialect_firebirdsql()
    assert dialect.type_compiler_instance.process(type_) == expected
    assert type_.dialect_impl(dialect).render_bind_cast


def test_bind_cast_places_type_inside_parentheses():
    dialect = FirebirdDialect_firebirdsql()
    compiler = dialect.statement_compiler(dialect, select(1))
    assert compiler.render_bind_cast(Date(), FirebirdDATE(), "?") == "CAST(? AS DATE)"


def test_union_ordering_uses_output_positions():
    source = table("source", column("id", Integer), column("data", Integer))
    statement = union(select(source), select(source)).order_by(source.c.data.desc(), source.c.id)
    sql = str(statement.compile(dialect=FirebirdDialect_firebirdsql()))
    assert sql.endswith(" ORDER BY 2 DESC, 1")


def test_union_ordering_resolves_label_without_mutating_statement():
    source = table("source", column("id", Integer))
    statement = union(select(source.c.id.label("item")), select(source.c.id)).order_by("item")
    assert str(statement.compile(dialect=FirebirdDialect_firebirdsql())).endswith(" ORDER BY 1")
    assert str(statement).endswith(" ORDER BY item")


def test_union_does_not_replace_columns_inside_functions():
    source = table("source", column("id", Integer))
    statement = union(select(source), select(source)).order_by(func.abs(source.c.id))
    sql = str(statement.compile(dialect=FirebirdDialect_firebirdsql()))
    assert sql.endswith(" ORDER BY abs(id)")


def test_simple_select_keeps_column_ordering():
    source = table("source", column("id", Integer))
    statement = select(source).order_by(source.c.id.desc())
    assert str(statement.compile(dialect=FirebirdDialect_firebirdsql())).endswith(" ORDER BY source.id DESC")
