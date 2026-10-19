"""Official suite with a schema-capability-aware reflection fixture."""
from sqlalchemy.testing.suite import *  # noqa: F401,F403
from sqlalchemy import (Column, Index, Integer, MetaData, String, Table, UniqueConstraint, cast, func, inspect, testing)
from sqlalchemy.testing.suite.test_reflection import (
    ComponentReflectionTestExtra as _ComponentReflectionTestExtra,
    ComponentReflectionTest as _ComponentReflectionTest,
    IdentityReflectionTest as _IdentityReflectionTest,
)


class ComponentReflectionTest(_ComponentReflectionTest):
    def exp_indexes(self, *args, **kw):
        expected = super().exp_indexes(*args, **kw)
        # Upstream adds address_id's named FK to dingalings, but omits its
        # backing index from exp_indexes on servers that create FK indexes.
        for (_, name), indexes in expected.items():
            if name == 'dingalings':
                indexes.append(dict(name='zz_email_add_id_fg', column_names=['address_id'], unique=False, dialect_options={}))
        return expected

    @testing.combinations((True, testing.requires.schemas), (False,), argnames='use_schema')
    def test_get_unique_constraints(self, metadata, connection, use_schema):
        schema = testing.config.test_schema if use_schema else None
        # Firebird rejects duplicate UNIQUE column sets regardless of order.
        # Keep overlapping multi-column constraints and noncanonical order,
        # using d instead of b in the second three-column constraint.
        definitions = {
            'unique_a': ['a'], 'unique_a_b_c': ['a', 'b', 'c'],
            'unique_c_a_d': ['c', 'a', 'd'], 'unique_asc_key': ['asc', 'key'],
            'i.have.dots': ['b'], 'i have spaces': ['c'],
        }
        table = Table('testtbl', metadata, *(Column(name, String(20)) for name in ('a', 'b', 'c', 'd', 'asc', 'key')), schema=schema)
        for name, columns in definitions.items():
            table.append_constraint(UniqueConstraint(*columns, name=name))
        table.create(connection)
        constraints = inspect(connection).get_unique_constraints('testtbl', schema=schema)
        assert {item['name']: item['column_names'] for item in constraints} == definitions
        reflected = Table('testtbl', MetaData(), autoload_with=connection, schema=schema)
        assert {constraint.name: [column.name for column in constraint.columns] for constraint in reflected.constraints if isinstance(constraint, UniqueConstraint)} == definitions
        assert not {index.name for index in reflected.indexes}.intersection(definitions)

    def _check_table_dict(self, result, exp, req_keys=None, make_lists=False):
        if req_keys == self._required_index_keys and not make_lists:
            # Server-generated FK/UNIQUE names do not share the order of
            # upstream's mock.ANY names. Compare the same complete records
            # in structural order, without hiding any reflected indexes.
            key = lambda index: (tuple(index['column_names']), index['unique'])
            result = {table: sorted(indexes, key=key) for table, indexes in result.items()}
            exp = {table: sorted(indexes, key=key) for table, indexes in exp.items()}
        return super()._check_table_dict(result, exp, req_keys, make_lists)


class IdentityReflectionTest(_IdentityReflectionTest):
    def check(self, value, exp, approx):
        # Firebird's identity grammar supports ALWAYS, START and INCREMENT,
        # not MINVALUE/MAXVALUE/CYCLE/CACHE. Do not invent metadata for them.
        assert value == {key: exp[key] for key in ('always', 'start', 'increment')}


class ComponentReflectionTestExtra(_ComponentReflectionTestExtra):
    def test_reflect_expression_based_indexes(self, metadata, connection):
        table = Table('t', metadata, *(Column(name, String(30)) for name in ('x', 'y', 'z')))
        Index('t_idx', func.lower(table.c.x), table.c.z, func.lower(table.c.y))
        long_string = 'long string ' * 100
        # Preserve long expression source, but bound the *result* key width
        # to fit Firebird's page-size-dependent limit (including UTF-8).
        Index('t_idx_long', cast(func.coalesce(table.c.x, long_string), String(100)))
        Index('t_idx_2', table.c.x)
        metadata.create_all(connection)
        indexes = inspect(connection).get_indexes('t')
        assert [index['name'] for index in indexes] == ['t_idx', 't_idx_2', 't_idx_long']
        assert all(not index['unique'] for index in indexes)
        assert indexes[0]['column_names'] == [None, 'z', None]
        assert indexes[0]['expressions'][0].lower() == 'lower(x)'
        assert indexes[0]['expressions'][2].lower() == 'lower(y)'
        assert indexes[1]['column_names'] == ['x']
        assert indexes[2]['column_names'] == [None]
        expression = indexes[2]['expressions'][0]
        assert 'coalesce' in expression.lower() and long_string in expression
        assert 'varchar(100)' in expression.lower()
        reflected = Table('t', MetaData(), autoload_with=connection)
        self.compare_table_index_with_expected(reflected, indexes, connection.engine.name)

    @testing.fixture(params=[True, False])
    def use_schema_fixture(self, request):
        # SQLAlchemy 2.1.4's upstream fixture does not consult requires.schemas.
        # Keep both cases executing, using the default namespace on backends
        # without schemas rather than emitting unsupported qualified DDL.
        if request.param and testing.requires.schemas.enabled:
            return testing.config.test_schema
        return None
