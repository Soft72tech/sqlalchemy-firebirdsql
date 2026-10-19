# TODO: investigate server side cursors
# TODO: connection characreristic


from typing import Any, List, Optional, cast

from sqlalchemy import Connection, exc, util
from sqlalchemy.engine import default, reflection
from sqlalchemy.engine.interfaces import (
    BindTyping,
    DBAPIConnection,
    ReflectedCheckConstraint,
    ReflectedColumn,
    ReflectedComputed,
    ReflectedForeignKeyConstraint,
    ReflectedIdentity,
    ReflectedIndex,
    ReflectedPrimaryKeyConstraint,
    ReflectedTableComment,
    ReflectedUniqueConstraint,
)
from sqlalchemy.sql import compiler, expression, sqltypes

from sqlalchemy_firebirdsql import types as fbtypes
from sqlalchemy_firebirdsql.compiler import FirebirdCompiler
from sqlalchemy_firebirdsql.ddl_compiler import FirebirdDDLCompiler
from sqlalchemy_firebirdsql.identifier_preparer import FirebirdIdentifierPreparer


class FirebirdTypeCompiler(compiler.GenericTypeCompiler):
    # TODO: implement
    def visit_datetime(self, type_: sqltypes.DateTime, **kw: Any) -> str:
        return self.visit_TIMESTAMP(type_, **kw)

    def visit_TIMESTAMP(self, type_, **kw):
        return "TIMESTAMP WITH TIME ZONE" if type_.timezone else "TIMESTAMP"

    def visit_TIME(self, type_, **kw):
        return "TIME WITH TIME ZONE" if type_.timezone else "TIME"

    def visit_boolean(self, type_: sqltypes.Boolean, **kw: Any) -> str:
        return super().visit_boolean(type_, **kw)

    def _render_string_type(self, name: str, length: Optional[int], collation: Optional[str], *args, **kw) -> str:
        return super()._render_string_type(name, length or 255, collation, *args, **kw)

    def visit_DOUBLE(self, type_, **kw):
        return "DOUBLE PRECISION"

    def visit_FLOAT(self, type_, **kw):
        if type_.precision is None:
            return "DOUBLE PRECISION"
        return f"FLOAT({type_.precision})"

    def visit_TEXT(self, type_, **kw):
        result = "BLOB SUB_TYPE TEXT"
        if type_.collation:
            result += " COLLATE " + self.dialect.identifier_preparer.quote(type_.collation)
        return result

    visit_CLOB = visit_TEXT
    visit_NCLOB = visit_TEXT

    def visit_JSON(self, type_, **kw):
        return "BLOB"

    def visit_ARRAY(self, type_, **kw):
        return "BLOB"


class FirebirdInspector(reflection.Inspector):
    dialect: "FirebirdDialect"
    # TODO: implement


class FirebirdExecutionContext(default.DefaultExecutionContext):
    def fire_sequence(self, seq, type_):
        return self._execute_scalar(
            "SELECT NEXT VALUE FOR "
            + self.identifier_preparer.format_sequence(seq)
            + " FROM rdb$database",
            type_,
        )


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
    # Firebird INSERT ... SELECT places WITH after the INSERT target list.
    cte_follows_insert = True
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

    bind_typing = BindTyping.RENDER_CASTS

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
        # RDB$TYPES reports storage names, not SQL declaration names.
        "short": sqltypes.SMALLINT,
        "long": sqltypes.INTEGER,
        "int64": sqltypes.BIGINT,
        "text": fbtypes.FirebirdCHARACTER,
        "varying": fbtypes.FirebirdVARCHAR,
        "double": sqltypes.DOUBLE_PRECISION,
        "time": sqltypes.TIME,
        "time with time zone": sqltypes.TIME,
        "timestamp": sqltypes.TIMESTAMP,
        "timestamp with time zone": sqltypes.TIMESTAMP,
        "varbinary": fbtypes.FirebirdVARBINARY,
        "binary varying": fbtypes.FirebirdVARBINARY,
        "varchar": fbtypes.FirebirdVARCHAR,
        "char varying": fbtypes.FirebirdVARCHAR,
        "character varying": fbtypes.FirebirdVARCHAR,
    }

    # TODO: all colspecs
    colspecs = {
        sqltypes.Integer: fbtypes.FirebirdInteger,
        sqltypes.BigInteger: fbtypes.FirebirdBIGINT,
        sqltypes.String: fbtypes.FirebirdString,
        sqltypes.VARCHAR: fbtypes.FirebirdVARCHAR,
        sqltypes.Numeric: fbtypes.FirebirdNumeric,
        sqltypes.DECIMAL: fbtypes.FirebirdDECIMAL,
        sqltypes.Float: fbtypes.FirebirdFLOAT,
        sqltypes.Double: fbtypes.FirebirdDOUBLE_PRECISION,
        sqltypes.ARRAY: fbtypes.FirebirdARRAY,
        sqltypes.BLOB: sqltypes.BLOB,
        sqltypes.DateTime: fbtypes.FirebirdTIMESTAMP,
        sqltypes.Date: fbtypes.FirebirdDATE,  # ?
        sqltypes.Time: fbtypes.FirebirdTIME,
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
    # TODO: check connection behaviorsfirerequ
    # TODO: readonly and deferrable

    def do_ping(self, dbapi_connection: DBAPIConnection) -> bool:
        return dbapi_connection.ping()

    @reflection.cache
    def has_table(
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
    ) -> bool:
        has_table_query = """
            SELECT 1 AS has_table
            FROM rdb$relations
            WHERE rdb$relation_name = ?
        """
        tablename = self.denormalize_name(table_name)

        return connection.exec_driver_sql(has_table_query, (tablename,)).first() is not None

    @reflection.cache
    def has_sequence(
        self,
        connection: Connection,
        sequence_name: str,
        schema: Optional[str] = None,
        **kw: Any,
    ) -> bool:
        query = """
            SELECT 1
            FROM rdb$generators
            WHERE rdb$generator_name = ?
              AND COALESCE(rdb$system_flag, 0) = 0
        """
        name = self.denormalize_name(sequence_name)
        return connection.exec_driver_sql(query, (name,)).first() is not None

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
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
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
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
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

        constraints = {}
        for row in cursor:
            name = self.normalize_name(row.cname)
            if name not in constraints:
                constraints[name] = ReflectedUniqueConstraint(name=name, column_names=[])
            constraints[name]["column_names"].append(self.normalize_name(row.column_name))

        if constraints:
            return list(constraints.values())

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.unique_constraints()

    @reflection.cache
    def get_pk_constraint(
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
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
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
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

                indexrec["dialect_options"] = {}
                if row.descending_flag:
                    indexrec["dialect_options"]["firebird_descending"] = True
                if row.condition_source is not None:
                    indexrec["dialect_options"]["firebird_where"] = row.condition_source

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

            return sorted(result, key=lambda index: index["name"])

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.indexes()

    @reflection.cache
    def get_foreign_keys(
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
    ) -> List[ReflectedForeignKeyConstraint]:
        fk_query = """
            SELECT TRIM(rc.rdb$constraint_name) AS cname,
                   TRIM(cse.rdb$field_name) AS fname,
                   TRIM(ix2.rdb$relation_name) AS targetrname,
                   TRIM(se.rdb$field_name) AS targetfname,
                   TRIM(rfc.rdb$update_rule) AS update_rule,
                   TRIM(rfc.rdb$delete_rule) AS delete_rule
            FROM rdb$relation_constraints rc
                 JOIN rdb$ref_constraints rfc 
                   ON rfc.rdb$constraint_name = rc.rdb$constraint_name
                 JOIN rdb$indices ix1 
                   ON ix1.rdb$index_name = rc.rdb$index_name
                 JOIN rdb$indices ix2 
                   ON ix2.rdb$index_name = ix1.rdb$foreign_key
                 JOIN rdb$index_segments cse 
                   ON cse.rdb$index_name = ix1.rdb$index_name
                 JOIN rdb$index_segments se 
                   ON se.rdb$index_name = ix2.rdb$index_name
                  AND se.rdb$field_position = cse.rdb$field_position
            WHERE rc.rdb$constraint_type = 'FOREIGN KEY'
              AND rc.rdb$relation_name = ?
            ORDER BY rc.rdb$constraint_name, se.rdb$field_position
        """
        tablename = self.denormalize_name(table_name)
        conn = connection.exec_driver_sql(fk_query, (tablename,))
        constraints = {}

        for row in conn:
            name = self.normalize_name(row.cname)

            if not (constraint := constraints.get(name)):
                constraint = ReflectedForeignKeyConstraint(
                    name=name,
                    constrained_columns=[],
                    # constrained_columns=[cast(str, self.normalize_name(row.fname))],
                    referred_schema=None,
                    referred_table=cast(str, self.normalize_name(row.targetrname)),
                    # referred_columns=[cast(str, self.normalize_name(row.targetfname))],
                    referred_columns=[],
                    options={
                        key: rule
                        for key, rule in (
                            ("onupdate", row.update_rule),
                            ("ondelete", row.delete_rule),
                        )
                        if rule not in (None, "NO ACTION", "RESTRICT")
                    },
                )
                constraints[name] = constraint

            constraint["constrained_columns"].append(cast(str, self.normalize_name(row.fname)))
            constraint["referred_columns"].append(cast(str, self.normalize_name(row.targetfname)))

        if result := list(constraints.values()):
            return result

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.foreign_keys()

    @reflection.cache
    def get_table_comment(
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
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

    @reflection.cache
    def get_table_names(self, connection: Connection, schema: Optional[str] = None, **kw: Any) -> List[str]:
        table_names_query = """
            SELECT TRIM(rdb$relation_name) AS relation_name
            FROM rdb$relations
            WHERE rdb$relation_type IN (0)
              AND COALESCE(rdb$system_flag, 0) = 0
            ORDER BY 1
        """

        return [
            cast(str, self.normalize_name(row.relation_name))
            for row in connection.exec_driver_sql(table_names_query)
        ]

    @reflection.cache
    def get_view_names(self, connection: Connection, schema=None, **kw):
        return [
            self.normalize_name(row[0])
            for row in connection.exec_driver_sql(
                "SELECT TRIM(rdb$relation_name) FROM rdb$relations "
                "WHERE rdb$relation_type = 1 "
                "AND COALESCE(rdb$system_flag, 0) = 0 ORDER BY 1"
            )
        ]

    @reflection.cache
    def get_view_definition(self, connection: Connection, view_name, schema=None, **kw):
        row = connection.exec_driver_sql(
            "SELECT rdb$view_source FROM rdb$relations "
            "WHERE rdb$relation_name = ? AND rdb$relation_type = 1",
            (self.denormalize_name(view_name),),
        ).first()
        if row is None:
            raise exc.NoSuchTableError(view_name)
        return row[0]

    @reflection.cache
    def get_temp_table_names(self, connection: Connection, schema=None, **kw):
        # RDB$RELATION_TYPE 4/5 are connection-/transaction-scoped GTTs.
        return [
            self.normalize_name(row[0])
            for row in connection.exec_driver_sql(
                "SELECT TRIM(rdb$relation_name) FROM rdb$relations "
                "WHERE rdb$relation_type IN (4, 5) "
                "AND COALESCE(rdb$system_flag, 0) = 0 ORDER BY 1"
            )
        ]

    @reflection.cache
    def get_temp_view_names(self, connection: Connection, schema=None, **kw):
        # Firebird has global temporary tables, but no temporary views.
        return []

    @reflection.cache
    def get_columns(
        self,
        connection: Connection,
        table_name: str,
        schema: Optional[str] = None,
        **kw: Any,
    ) -> List[ReflectedColumn]:
        columns_query = """
            SELECT TRIM(rf.rdb$field_name) AS field_name,
                   COALESCE(rf.rdb$null_flag, f.rdb$null_flag) AS null_flag,
                   TRIM(t.rdb$type_name) AS field_type,
                   f.rdb$field_length / COALESCE(cs.rdb$bytes_per_character, 1) AS field_length,
                   f.rdb$field_precision AS field_precision,
                   f.rdb$field_scale * -1 AS field_scale,
                   f.rdb$field_sub_type AS field_sub_type,
                   f.rdb$segment_length AS segment_length,
                   TRIM(cs.rdb$character_set_name) as character_set_name,
                   TRIM(cl.rdb$collation_name) as collation_name,
                   COALESCE(rf.rdb$default_source, f.rdb$default_source) AS default_source,
                   TRIM(rf.rdb$description) AS description,
                   f.rdb$computed_source AS computed_source
                  ,rf.rdb$identity_type AS identity_type,                      
                   g.rdb$initial_value AS initial_value,                       
                   g.rdb$generator_increment AS generator_increment            
            FROM rdb$relation_fields rf
                 JOIN rdb$fields f
                   ON f.rdb$field_name = rf.rdb$field_source
                 JOIN rdb$types t
                   ON t.rdb$type = f.rdb$field_type 
                  AND t.rdb$field_name = 'RDB$FIELD_TYPE'
                 LEFT JOIN rdb$character_sets cs
                        ON cs.rdb$character_set_id = f.rdb$character_set_id
                 LEFT JOIN rdb$collations cl
                        ON cl.rdb$collation_id = rf.rdb$collation_id
                       AND cl.rdb$character_set_id = cs.rdb$character_set_id
                 LEFT JOIN rdb$generators g                                    
                        ON g.rdb$generator_name = rf.rdb$generator_name        
            WHERE COALESCE(f.rdb$system_flag, 0) = 0
              AND rf.rdb$relation_name = ?
            ORDER BY rf.rdb$field_position
        """

        tablename = self.denormalize_name(table_name)
        cursor = connection.exec_driver_sql(columns_query, (tablename,))

        def match_column_type(row):
            column_cls = self.ischema_names.get(row.field_type.lower())

            match column_cls:
                case fbtypes.FirebirdCHARACTER | fbtypes.FirebirdVARCHAR:
                    match (column_cls, row.character_set_name):
                        case (fbtypes.FirebirdCHARACTER, "OCTETS"):
                            column_type = fbtypes.FirebirdBINARY(
                                length=row.field_length,
                                charset=row.character_set_name,
                            )
                        case (fbtypes.FirebirdVARCHAR, "OCTETS"):
                            column_type = fbtypes.FirebirdVARCHAR(
                                length=row.field_length,
                                charset=row.character_set_name,
                                collation=row.collation_name,
                            )
                        case (fbtypes.FirebirdCHARACTER, "ISO8859_1"):
                            column_type = fbtypes.FirebirdNCHAR(
                                length=row.field_length,
                                charset=row.character_set_name,
                                collation=row.collation_name,
                            )
                        case (fbtypes.FirebirdVARCHAR, "ISO8859_1"):
                            column_type = fbtypes.FirebirdNVARCHAR(
                                length=row.field_length,
                                charset=row.character_set_name,
                                collation=row.collation_name,
                            )

                        case _:
                            column_type = column_cls(
                                length=row.field_length,
                                charset=row.character_set_name,
                                collation=row.collation_name,
                            )

                case sqltypes.NUMERIC:
                    column_type = fbtypes.FirebirdNumeric(precision=row.field_precision)

                case (
                    sqltypes.INT | sqltypes.INTEGER | sqltypes.SMALLINT
                    | sqltypes.BIGINT | fbtypes.FirebirdINT128
                ):
                    match row.field_sub_type:
                        case 0:
                            column_type = column_cls()
                        case 1:
                            column_type = sqltypes.NUMERIC(
                                precision=row.field_precision, scale=row.field_scale
                            )
                        case _:
                            column_type = fbtypes.FirebirdDECIMAL(
                                precision=row.field_precision, scale=row.field_scale
                            )

                case sqltypes.TIME | sqltypes.TIMESTAMP:
                    column_type = column_cls(timezone="WITH TIME ZONE" in row.field_type)

                case fbtypes.FirebirdLargeBinary:
                    match row.field_sub_type:
                        case 1:
                            column_type = fbtypes.FirebirdTEXT(
                                length=row.segment_length,
                                charset=row.character_set_name,
                                collation=row.collation_name,
                            )

                case None:
                    column_type = sqltypes.NULLTYPE

                case _:
                    column_type = column_cls()

            return column_type

        if result := [
            ReflectedColumn(
                name=cast(str, self.normalize_name(row.field_name)),
                type=match_column_type(row),
                nullable=not bool(row.null_flag),
                default=row.default_source.replace("default", "").replace("DEFAULT", "").trim()
                if row.default_source
                else None,
                # Do not override SQLAlchemy's PK autoincrement inference for
                # ordinary columns; identity metadata is the positive signal.
                **({"autoincrement": True} if row.identity_type is not None else {}),
                comment=row.description,
                computed=ReflectedComputed(sqltext=row.computed_source) if row.computed_source else None,
                identity=ReflectedIdentity(
                    always=row.identity_type == 0,
                    start=row.initial_value,
                    increment=row.generator_increment,
                )
                if row.identity_type
                else None,
            )
            for row in cursor
        ]:
            return result

        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(table_name)

        return reflection.ReflectionDefaults.columns()
