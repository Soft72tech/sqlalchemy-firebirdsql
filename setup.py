entry_points = {
    "sqlalchemy.dialects": [
        "firebird.firebirdsql = sqlalchemy_firebird.pyodbc:AccessDialect_pyodbc",
    ]
}