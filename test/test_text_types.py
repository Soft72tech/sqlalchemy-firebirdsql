import pytest
from sqlalchemy import CLOB, Text, UnicodeText, Column, MetaData, Table
from sqlalchemy.schema import CreateTable
from sqlalchemy_firebirdsql.firebirdsql import FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('type_', [Text(), Text(255), UnicodeText(), CLOB()])
def test_text_ddl_is_text_blob(dialect_cls, type_):
    table = Table('text_data', MetaData(), Column('value', type_))
    sql = str(CreateTable(table).compile(dialect=dialect_cls()))
    assert 'BLOB SUB_TYPE TEXT' in sql
    assert 'TEXT(255)' not in sql
