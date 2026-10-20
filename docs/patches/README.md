# SQLAlchemy CTAS capability guard

`sqlalchemy-2.1.4-ctas-capability.patch` is a proposed upstream test fix for SQLAlchemy 2.1.4, not a Firebird implementation of CTAS. Nothing has been submitted upstream.

Two plain combinations in `TableViaSelectTest.test_without_metadata` execute CTAS without checking `requires.create_table_as`. Both have `use_view=False`; the existing view combinations are untouched. The patch applies the existing requirement only to those two cases. Backends that enable this requirement retain those tests. Firebird inherits the closed default; no dialect override is necessary.

Apply to a SQLAlchemy source checkout:

```sh
git apply /absolute/path/to/sqlalchemy-2.1.4-ctas-capability.patch
```

Or apply to the project's baseline environment from the dialect repository:

```sh
patch --batch -p2 -d .venv-baseline/lib/python3.13/site-packages < docs/patches/sqlalchemy-2.1.4-ctas-capability.patch
```

The baseline environment currently has this patch applied. Reinstalling SQLAlchemy removes it. Reverse with the same command plus `-R`. Do not apply it twice.

Verified locally against Firebird 5 using the existing baseline database: `TableViaSelectTest` sync and async each **7 passed, 24 skipped, 1485 deselected**. The two formerly failing CTAS cases now skip; existing view tests pass. Logs: `baseline/phase-ctas-guard-firebirdsql.log` and `baseline/phase-ctas-guard-firebirdsql_async.log`. Full official suite subsequently passed for both sync and async: each **1017 passed, 499 skipped**, no failures/errors (139.48 / 144.55 s). Logs: `baseline/phase-ctas-guard-full-firebirdsql.log` and `baseline/phase-ctas-guard-full-firebirdsql_async.log`. Command from the dialect repository, repeated with `DRIVER=firebirdsql` and `DRIVER=firebirdsql_async`:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout -k 2 240 .venv-baseline/bin/python -m pytest test/test_official_suite.py --maxfail=0 --dburi "firebird+$DRIVER://SYSDBA:root@127.0.0.1:13050//var/lib/firebird/data/phase1.fdb" --tb=short
```

Other database backends were not rerun. This is an explicit upstream-suite adaptation, not a driver defect fix.
