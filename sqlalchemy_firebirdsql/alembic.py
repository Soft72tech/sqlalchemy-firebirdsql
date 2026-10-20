"""Optional Alembic integration. Import this module from migration env.py."""

from alembic.ddl import base
from alembic.ddl.impl import DefaultImpl
from sqlalchemy import exc
from sqlalchemy.ext.compiler import compiles


class FirebirdImpl(DefaultImpl):
    __dialect__ = 'firebird'
    transactional_ddl = True


def _table(element, compiler):
    if element.schema is not None:
        raise exc.CompileError('Firebird does not support SQL schemas')
    return base.alter_table(compiler, element.table_name, None)


@compiles(base.AddColumn, 'firebird')
def add_column(element, compiler, **kw):
    if element.if_not_exists:
        raise exc.CompileError('Firebird 5 ADD does not support IF NOT EXISTS')
    # Reuse Alembic constraint rendering, replacing only its SQL prefix.
    definition = base.add_column(
        compiler, element.column,
        inline_references=element.inline_references,
        inline_primary_key=element.inline_primary_key, **kw)
    return _table(element, compiler) + ' ADD ' + definition[len('ADD COLUMN '):]


@compiles(base.DropColumn, 'firebird')
def drop_column(element, compiler, **kw):
    if element.if_exists:
        raise exc.CompileError('Firebird 5 DROP does not support IF EXISTS')
    return _table(element, compiler) + ' DROP ' + base.format_column_name(compiler, element.column.name)


@compiles(base.ColumnName, 'firebird')
def rename_column(element, compiler, **kw):
    return '%s ALTER COLUMN %s TO %s' % (
        _table(element, compiler),
        base.format_column_name(compiler, element.column_name),
        base.format_column_name(compiler, element.newname))


@compiles(base.RenameTable, 'firebird')
def rename_table(element, compiler, **kw):
    raise exc.CompileError('Firebird 5 does not support renaming tables')
