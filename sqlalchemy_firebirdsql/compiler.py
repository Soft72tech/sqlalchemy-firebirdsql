import re

from sqlalchemy import exc, literal_column, type_coerce
from sqlalchemy.sql import compiler, elements, selectable, sqltypes, visitors


class FirebirdCompiler(compiler.SQLCompiler):
    def visit_over(self, over, **kw):
        frame = over.range_
        # FrameClause is new in SQLAlchemy 2.1; leave 2.0 tuple frames alone.
        if frame is not None and hasattr(frame, 'lower_bind'):
            bounds = (frame.lower_bind, frame.upper_bind)
            if any(bind is not None and isinstance(bind.type, sqltypes.Interval)
                   for bind in bounds):
                from .types import _FirebirdRangeOffset

                order = list(over.order_by) if over.order_by is not None else []
                if len(order) != 1:
                    raise exc.CompileError('Temporal RANGE requires one typed ORDER BY expression')
                expression = order[0]
                while isinstance(expression, elements.UnaryExpression):
                    expression = expression.element
                type_ = expression.type
                if isinstance(type_, sqltypes.DateTime):
                    unit = 'timestamp'
                elif isinstance(type_, sqltypes.Date):
                    unit = 'date'
                elif isinstance(type_, sqltypes.Time):
                    unit = 'time'
                else:
                    raise exc.CompileError('timedelta RANGE requires DATE, TIME or TIMESTAMP ordering')
                frame = frame._clone()
                for name in ('lower_bind', 'upper_bind'):
                    bind = getattr(frame, name)
                    if bind is not None and isinstance(bind.type, sqltypes.Interval):
                        setattr(frame, name, type_coerce(bind, _FirebirdRangeOffset(unit)))
                over = over._clone()
                over.range_ = frame
        return super().visit_over(over, **kw)

    def render_bind_cast(self, type_, dbapi_type, sqltext) -> str:
        if isinstance(dbapi_type, sqltypes.String):
            # The compared column length is not a bound on a LIKE pattern or
            # concatenation operand. Text BLOBs avoid silent truncation.
            return f"CAST({sqltext} AS BLOB SUB_TYPE TEXT)"
        if isinstance(dbapi_type, sqltypes.Numeric) and not isinstance(dbapi_type, sqltypes.Float) and dbapi_type.precision is None:
            # Unconstrained Decimal binds must not acquire NUMERIC's default
            # scale zero. DECFLOAT keeps fractional values and exponents.
            if dbapi_type.scale is None:
                return f"CAST({sqltext} AS DECFLOAT(34))"
            dbapi_type = sqltypes.Numeric(38, dbapi_type.scale)
        type_sql = self.dialect.type_compiler_instance.process(
            dbapi_type, identifier_preparer=self.preparer
        )
        return f"CAST({sqltext} AS {type_sql})"

    def order_by_clause(self, select, **kw):
        if not isinstance(select, selectable.CompoundSelect):
            return super().order_by_clause(select, **kw)

        # Firebird Language Reference, Ordering UNION-ed Sets: ordinal column
        # positions work even where an unaliased output name is rejected.
        columns = list(select.selected_columns)

        def ordinal(node):
            if isinstance(node, (elements.ClauseList, elements.UnaryExpression, elements._label_reference)):
                return None
            if isinstance(node, elements._textual_label_reference):
                for position, column in enumerate(columns, 1):
                    if node.element in (column.key, column.name):
                        return literal_column(str(position))
            elif isinstance(node, elements.ColumnClause):
                for position, column in enumerate(columns, 1):
                    if column.shares_lineage(node):
                        return literal_column(str(position))
            # Do not substitute inside functions/arithmetic: abs(id) is not
            # equivalent to abs(1), where 1 is a SELECT-list position.
            return node

        clauses = visitors.replacement_traverse(select._order_by_clause, {}, ordinal)
        text = self.process(clauses, **kw)
        return " ORDER BY " + text if text else ""

    def visit_empty_set_expr(self, element_types, **kwargs) -> str:
        return "SELECT 1 FROM rdb$database WHERE 1 != 1"

    def default_from(self) -> str:
        return " FROM rdb$database"

    def for_update_clause(self, select, **kw):
        for_update_clause = super().for_update_clause(select, **kw)

        if select._for_update_args.nowait:
            for_update_clause = f"{for_update_clause} WITH LOCK"

        if select._for_update_args.skip_locked:
            for_update_clause = f"{for_update_clause} WITH LOCK SKIP LOCKED"

        return for_update_clause

    def visit_sequence(self, sequence, **kwargs) -> str:
        return f"NEXT VALUE FOR {self.preparer.format_sequence(sequence)}"

    def visit_substring_func(self, func, **kwargs) -> str:
        s = self.process(func.clauses.clauses[0], **kwargs)
        start = self.process(func.clauses.clauses[1], **kwargs)

        if len(func.clauses.clauses) > 2:
            length = self.process(func.clauses.clauses[2], **kwargs)

            return f"SUBSTRING({s} FROM {start} FOR {length})"

        else:
            return f"SUBSTRING({s} FROM {start})"

    def visit_cast(self, cast, **kw):
        clause = cast.clause
        if (
            isinstance(cast.type, sqltypes.Numeric)
            and not isinstance(cast.type, sqltypes.Float)
            and (cast.type.precision or 0) > 34
            and isinstance(clause, elements.ColumnClause)
            and clause.is_literal
            and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", clause.name)
        ):
            # Firebird 5 can misconvert a nested 38-digit numeric literal
            # through DECFLOAT during expression evaluation. Parsing the
            # same decimal text into the declared exact type avoids it.
            value = self.render_literal_value(clause.name, sqltypes.String())
            return f"CAST({value} AS {self.process(cast.typeclause, **kw)})"
        return super().visit_cast(cast, **kw)

    def visit_truediv_binary(self, binary, operator, **kw):
        # Integer / integer truncates in Firebird. Fixed NUMERIC casts can
        # also truncate unknown-scale divisors or overflow large operands.
        target = "DOUBLE PRECISION" if isinstance(binary.left.type, sqltypes.Float) else "DECFLOAT(34)"
        left = self.process(binary.left, **kw)
        right = self.process(binary.right, **kw)
        return f"CAST({left} AS {target}) / CAST({right} AS {target})"

    def visit_mod_binary(self, binary, operator, **kw):
        return f"MOD({self.process(binary.left, **kw)}, {self.process(binary.right, **kw)})"

    def visit_bitwise_xor_op_binary(self, binary, operator, **kw):
        return f"BIN_XOR({self.process(binary.left, **kw)}, {self.process(binary.right, **kw)})"

    def visit_now_func(self, func, **kw):
        return "CURRENT_TIMESTAMP"

    def visit_char_length_func(self, fn, **kw):
        return f"CHAR_LENGTH{self.function_argspec(fn, **kw)}"

    def visit_length_func(self, fn, **kw):
        return f"CHAR_LENGTH{self.function_argspec(fn, **kw)}"

    def limit_clause(self, select, **kw):
        return self.fetch_clause(select, **kw)

    def fetch_clause(
        self,
        select,
        fetch_clause=None,
        require_offset=False,
        use_literal_execute_for_simple_int=False,
        **kw,
    ):
        """
        Generate Firebird-specific pagination using ROWS m TO n syntax.

        Supports:
        - offset + limit: ROWS offset+1 TO offset+limit
        - offset only: ROWS offset+1 TO max big int
        - limit only: ROWS 1 TO limit
        """

        if fetch_clause is None:
            if select._limit_clause is not None:
                fetch_clause = select._limit_clause
            else:
                fetch_clause = select._fetch_clause
        offset_clause = select._offset_clause

        if offset_clause is not None and fetch_clause is not None:
            fetch_str = self.process(fetch_clause, **kw)
            offset_str = self.process(offset_clause, **kw)
            return f" ROWS {offset_str} + 1 TO {offset_str} + {fetch_str}"
        elif offset_clause is not None:
            offset_str = self.process(offset_clause, **kw)
            return f" ROWS {offset_str} + 1 TO 9223372036854775807"  # max bigint
        elif fetch_clause is not None:
            fetch_str = self.process(fetch_clause, **kw)
            return f" ROWS 1 TO {fetch_str}"
        return ""

    # TODO: check other possible visit_* methods with docs
