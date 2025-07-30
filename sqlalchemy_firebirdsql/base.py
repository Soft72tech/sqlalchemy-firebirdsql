# TODO: investigate server side cursors
# TODO: connection characreristic


from typing import Any, List, Optional, cast

from sqlalchemy import Connection, exc, util
from sqlalchemy.engine import default, reflection
from sqlalchemy.engine.interfaces import (
    ReflectedCheckConstraint,
    ReflectedIndex,
    ReflectedPrimaryKeyConstraint,
    ReflectedTableComment,
    ReflectedUniqueConstraint,
    DBAPIConnection,
)
from sqlalchemy.sql import compiler, expression, sqltypes

from sqlalchemy_firebirdsql import types as fbtypes
from sqlalchemy_firebirdsql.compiler import FirebirdCompiler
from sqlalchemy_firebirdsql.ddl_compiler import FirebirdDDLCompiler
from sqlalchemy_firebirdsql.identifier_preparer import FirebirdIdentifierPreparer


class FirebirdTypeCompiler(compiler.GenericTypeCompiler):
    # TODO: implement

    def visit_datetime(self, type_: sqltypes.DateTime, **kw: Any) -> str:
        return super().visit_datetime(type_, **kw)

    def visit_boolean(self, type_: sqltypes.Boolean, **kw: Any) -> str:
        return super().visit_boolean(type_, **kw)


class FirebirdInspector(reflection.Inspector):
    dialect: "FirebirdDialect"
    # TODO: implement


class FirebirdExecutionContext(default.DefaultExecutionContext):
    # TODO: implement
    ...


class FirebirdDialect(default.DefaultDialect):
    name = "firebird"

    max_identifier_length = 63

    supports_statement_cache = True
    supports_alter = True
    supports_sane_rowcount = True
    supports_sane_multi_rowcount = False

    supports_native_boolean = True
    supports_native_decimal = True
    supports_native_enum = False
    supports_native_uuid = False

    supports_schemas = False
    supports_sequences = True
    sequences_optional = False
    supports_comments = True
    supports_default_values = True
    supports_default_metavalue = True
    supports_identity_columns = True
    supports_empty_insert = False
    supports_is_distinct_from = True

    postfetch_lastrowid = False
    use_insertmanyvalues = False
    requires_name_normalize = True

    update_returning = True
    delete_returning = True
    insert_returning = True

    execution_ctx_cls = FirebirdExecutionContext

    statement_compiler = FirebirdCompiler
    ddl_compiler = FirebirdDDLCompiler
    type_compiler_cls = FirebirdTypeCompiler
    preparer = FirebirdIdentifierPreparer

    ischema_names = {
        "bigint": sqltypes.BIGINT,
        "blob": sqltypes.BLOB,
        "boolean": sqltypes.BOOLEAN,
        "character": fbtypes.FirebirdCHARACTER,
        "char": sqltypes.CHAR,
        "date": fbtypes.FirebirdDATE,
        "decfloat": fbtypes.FirebirdDECFLOAT,
        "decimal": sqltypes.DECIMAL,
        "double precision": sqltypes.DOUBLE_PRECISION,
        "float": sqltypes.FLOAT,
        "integer": sqltypes.INTEGER,
        "int": sqltypes.INT,
        "int128": fbtypes.FirebirdINT128,
        "numeric": sqltypes.NUMERIC,
        "real": sqltypes.REAL,
        "smallint": sqltypes.SMALLINT,
        "time": sqltypes.TIME,
        "time with time zone": sqltypes.TIME(timezone=True),
        "timestamp": sqltypes.TIMESTAMP,
        "timestamp with time zone": sqltypes.TIMESTAMP(timezone=True),
        "varbinary": fbtypes.FirebirdVARBINARY,
        "binary varying": fbtypes.FirebirdVARBINARY,
        "varchar": fbtypes.FirebirdVARCHAR,
        "char varying": fbtypes.FirebirdVARCHAR,
        "character varying": fbtypes.FirebirdVARCHAR,
    }

    # TODO: all colspecs
    colspecs = {
        sqltypes.BigInteger: sqltypes.BIGINT,
        sqltypes.BLOB: sqltypes.BLOB,
        sqltypes.DateTime: sqltypes.TIMESTAMP,
        sqltypes.Date: fbtypes.FirebirdDATE,  # ?
        sqltypes.Time: sqltypes.TIME,
    }

    construct_arguments = [(reflection.sa_schema.Table, {"on_commit": None})]

    @classmethod
    def import_dbapi(cls):
        # Implemented at the driver level
        raise NotImplementedError()

    def create_connect_args(self, url):
        opts = url.translate_connect_args(username="user")
        return ([], opts)

    # TODO: isolation level
    # TODO: check connection behaviors
    # TODO: readonly and deferrable

    def do_ping(self, dbapi_connection: DBAPIConnection) -> bool:
        return dbapi_connection.ping()

    @reflection.cache
    def has_table(
        self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw: Any
    ) -> bool:
        has_table_query = """
            SELECT 1 AS has_table
            FROM rdb$relations
            WHERE rdb$relation_name = ?
        """
        tablename = self.denormalize_name(table_name)

        return connection.exec_driver_sql(has_table_query, (tablename,)).first() is not None

    @reflection.cache
    def get_sequence_names(
        self, connection: Connection, schema: Optional[str] = None, **kw: Any
    ) -> List[str]:
        sequences_query = """
            SELECT TRIM(rdb$generator_name) AS generator_name
            FROM rdb$generators
            WHERE COALESCE(rdb$system_flag, 0) = 0
        """

        # Do not need ORDER BY
        return [
            cast(str, self.normalize_name(row.generator_name))
            for row in connection.exec_driver_sql(sequences_query)
        ]

    @reflection.cache
    def get_check_constraints(
        self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw: Any
    ) -> List[ReflectedCheckConstraint]:
        check_constraints_query = """
            SELECT TRIM(rc.rdb$constraint_name) AS cname,
                   TRIM(SUBSTRING(tr.rdb$trigger_source FROM 8 FOR CHAR_LENGTH(tr.rdb$trigger_source) - 8)) AS sqltext
            FROM rdb$relation_constraints rc
                 JOIN rdb$check_constraints ck
                   ON ck.rdb$constraint_name = rc.rdb$constraint_name
                 JOIN rdb$triggers tr
                   ON tr.rdb$trigger_name = ck.rdb$trigger_name AND
                      tr.rdb$trigger_type = 1 /* BEFORE UPDATE */
            WHERE rc.rdb$constraint_type = 'CHECK' AND
                  rc.rdb$relation_name = ?
            ORDER BY 1
        """
        tablename = self.denormalize_name(table_name)
        cursor = connection.exec_driver_sql(check_constraints_query, (tablename,))

        if result := [
            ReflectedCheckConstraint(name=self.normalize_name(row.cname), sqltext=row.sqltext)
            for row in cursor
        ]:
            return result

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.check_constraints()

    @reflection.cache
    def get_unique_constraints(
        self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw: Any
    ) -> List[ReflectedUniqueConstraint]:
        unique_constraints_query = """
            SELECT TRIM(rc.rdb$constraint_name) AS cname,
                TRIM(se.rdb$field_name) AS column_name
            FROM rdb$index_segments se
                JOIN rdb$relation_constraints rc
                    ON rc.rdb$index_name = se.rdb$index_name
                JOIN rdb$relations r
                    ON r.rdb$relation_name = rc.rdb$relation_name
                    AND COALESCE(r.rdb$system_flag, 0) = 0
            WHERE rc.rdb$constraint_type = 'UNIQUE'
                AND r.rdb$relation_name = ?
            ORDER BY rc.rdb$constraint_name, se.rdb$field_position
        """
        tablename = self.denormalize_name(table_name)

        cursor = connection.exec_driver_sql(unique_constraints_query, (tablename,))

        if result := [
            ReflectedUniqueConstraint(name=self.normalize_name(row.cname), column_names=[row.column_name])
            for row in cursor
        ]:
            return result

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.unique_constraints()

    @reflection.cache
    def get_pk_constraint(
        self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw: Any
    ) -> ReflectedPrimaryKeyConstraint:
        pk_query = """
            SELECT TRIM(rc.rdb$constraint_name) AS cname, TRIM(se.rdb$field_name) AS fname
            FROM rdb$relation_constraints rc
                JOIN rdb$index_segments se
                   ON se.rdb$index_name = rc.rdb$index_name
            WHERE rc.rdb$constraint_type = 'PRIMARY KEY'
                AND rc.rdb$relation_name = ?
            ORDER BY se.rdb$field_position
        """
        tablename = self.denormalize_name(table_name)

        cursor = connection.exec_driver_sql(pk_query, (tablename,))

        if rows := cursor.fetchall():
            return ReflectedPrimaryKeyConstraint(
                constrained_columns=[cast(str, self.normalize_name(row.fname)) for row in rows],
                name=self.normalize_name(rows[0].cname),
            )

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.pk_constraint()

    @reflection.cache
    def get_indexes(
        self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw: Any
    ) -> List[ReflectedIndex]:
        condition_source_expr = (
            "TRIM(SUBSTRING(ix.rdb$condition_source FROM 6 FOR CHAR_LENGTH(ix.rdb$condition_source) - 5))"
        )

        indexes_query = f"""
            SELECT TRIM(ix.rdb$index_name) AS index_name,
                   ix.rdb$unique_flag AS unique_flag,
                   ix.rdb$index_type AS descending_flag,
                   TRIM(ic.rdb$field_name) AS field_name,
                   TRIM(ix.rdb$expression_source) expression_source,
                   {condition_source_expr} condition_source
            FROM rdb$indices ix
                LEFT OUTER JOIN rdb$index_segments ic
                  ON ic.rdb$index_name = ix.rdb$index_name
                LEFT OUTER JOIN rdb$relation_constraints rc
                             ON rc.rdb$index_name = ic.rdb$index_name
            WHERE ix.rdb$relation_name = :relation_name
              AND ix.rdb$foreign_key IS NULL
              AND COALESCE(rc.rdb$constraint_type, '') <> 'PRIMARY KEY'
            ORDER BY ix.rdb$index_name, ic.rdb$field_position
        """
        tablename = self.denormalize_name(table_name)

        # Do not use connection.exec_driver_sql() here.
        #    During tests we need to commit CREATE INDEX before this query.
        cursor = connection.execute(expression.text(indexes_query), {"relation_name": tablename})

        indexes = util.defaultdict(dict)

        for row in cursor:
            indexrec = indexes[row.index_name]

            if "name" not in indexrec:
                indexrec["name"] = self.normalize_name(row.index_name)
                indexrec["column_names"] = []
                indexrec["unique"] = bool(row.unique_flag)

                if row.expression_source is not None:
                    expr = row.expression_source[1:-1]  # Remove outermost parenthesis added by Firebird
                    indexrec["expressions"] = expr.split("||")

                indexrec["dialect_options"] = {
                    "firebird_descending": bool(row.descending_flag),
                    "firebird_where": row.condition_source,
                }

            indexrec["column_names"].append(self.normalize_name(row.field_name))

        if result := [ReflectedIndex(**index) for index in indexes.values()]:
            # Identify which expression elements are columns
            colqry = """
                SELECT TRIM(r.rdb$field_name) AS fname
                FROM rdb$relation_fields r
                WHERE r.rdb$relation_name = ?
            """

            colset = {
                self.normalize_name(row.fname) for row in connection.exec_driver_sql(colqry, (tablename,))
            }

            for index in result:
                if expr := index.get("expressions"):
                    index["column_names"] = [x if self.normalize_name(x) in colset else None for x in expr]

            return result

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.indexes()

    @reflection.cache
    def get_table_comment(
        self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw: Any
    ) -> ReflectedTableComment:
        table_comment_query = """
            SELECT TRIM(rdb$description) AS comment
            FROM rdb$relations
            WHERE rdb$relation_name = ?
        """
        tablename = self.denormalize_name(table_name)

        if result := connection.exec_driver_sql(table_comment_query, (tablename,)).fetchone():
            return ReflectedTableComment(text=result[0])

        raise exc.NoSuchTableError(table_name)
