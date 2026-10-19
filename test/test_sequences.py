from sqlalchemy import BigInteger, Sequence, select
import pytest

from sqlalchemy_firebirdsql.base import FirebirdExecutionContext
from sqlalchemy_firebirdsql.firebirdsql import (
    FirebirdDialect_firebirdsql,
    FirebirdDialectAsync_firebirdsql,
)


@pytest.mark.parametrize("dialect_cls", [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
def test_sequence_uses_configured_increment(dialect_cls):
    dialect = dialect_cls()
    sequence = Sequence("Odd Sequence", start=2, increment=3)
    compiled = str(select(sequence.next_value()).compile(dialect=dialect))
    assert 'NEXT VALUE FOR "Odd Sequence"' in compiled
    assert "GEN_ID" not in compiled

    context = object.__new__(FirebirdExecutionContext)
    context.identifier_preparer = dialect.identifier_preparer
    calls = []
    context._execute_scalar = lambda statement, type_: calls.append((statement, type_)) or 2
    type_ = BigInteger()
    assert context.fire_sequence(sequence, type_) == 2
    assert calls == [('SELECT NEXT VALUE FOR "Odd Sequence" FROM rdb$database', type_)]
