from sqlalchemy.sql import compiler


class FirebirdCompiler(compiler.SQLCompiler):
    def render_bind_cast(self, type_, dbapi_type, sqltext) -> str:
        return f"""CAST({sqltext}) AS {
            self.dialect.type_compiler_instance.process(dbapi_type, identifier_preparer=self.preparer)
        }"""

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
        return f"GEN_ID({self.preparer.format_sequence(sequence)}, 1)"

    def visit_substring_func(self, func, **kwargs) -> str:
        s = self.process(func.clauses.clauses[0], **kwargs)
        start = self.process(func.clauses.clauses[1], **kwargs)

        if len(func.clauses.clauses) > 2:
            length = self.process(func.clauses.clauses[2], **kwargs)

            return f"SUBSTRING({s} FROM {start} FOR {length})"

        else:
            return f"SUBSTRING({s} FROM {start})"

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
