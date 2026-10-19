"""Firebird-specific support for SQLAlchemy's external dialect suite."""
from sqlalchemy import inspect
from sqlalchemy.testing import provision


@provision.temp_table_keyword_args.for_db("firebird")
def temp_table_keyword_args(cfg, engine):
    # Firebird 5 Language Reference §5.4.1: metadata is persistent, while
    # ON COMMIT PRESERVE ROWS scopes the data to the connection.
    return {"prefixes": ["GLOBAL TEMPORARY"], "firebird_on_commit": "PRESERVE ROWS"}


@provision.delete_from_all_tables.for_db("firebird")
def delete_from_all_tables(connection, cfg, metadata):
    # Firebird checks self-referencing foreign keys during DELETE. Disconnect
    # nullable self references before the suite's ordinary table cleanup so a
    # parent encountered before its children cannot leave the fixture populated.
    inspector = inspect(connection)
    for table in metadata.tables.values():
        if table.name not in inspector.get_table_names(schema=table.schema):
            continue
        nullable_self_refs = {
            fk.parent: None
            for fk in table.foreign_keys
            if fk.column.table is table and fk.parent.nullable
        }
        if nullable_self_refs:
            connection.execute(table.update().values(nullable_self_refs))
    return provision.delete_from_all_tables.call_original(connection, cfg, metadata)
