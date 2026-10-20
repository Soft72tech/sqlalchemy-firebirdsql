import pytest
from sqlalchemy import Column, Integer, exc

pytest.importorskip('alembic')
from alembic.ddl import base
import sqlalchemy_firebirdsql.alembic  # noqa: F401
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql


def compile_ddl(statement):
    return str(statement.compile(dialect=FirebirdDialect_firebirdsql()))


def test_firebird_column_ddl():
    assert compile_ddl(base.AddColumn('sample', Column('value', Integer))) == 'ALTER TABLE sample ADD "value" INTEGER'
    assert compile_ddl(base.DropColumn('sample', Column('value', Integer))) == 'ALTER TABLE sample DROP "value"'
    assert compile_ddl(base.ColumnName('sample', 'value', 'new_value')) == 'ALTER TABLE sample ALTER COLUMN "value" TO new_value'


@pytest.mark.parametrize('statement', [
    base.AddColumn('sample', Column('x', Integer), if_not_exists=True),
    base.DropColumn('sample', Column('x', Integer), if_exists=True),
    base.AddColumn('sample', Column('x', Integer), schema='other'),
    base.RenameTable('sample', 'other'),
])
def test_unsupported_migration_ddl_is_explicit(statement):
    with pytest.raises(exc.CompileError):
        compile_ddl(statement)
