# Локальная сборка и проверка

Проверенный стек: Python 3.13.5, SQLAlchemy 2.1.4, greenlet 3.5.6, Alembic 1.18.4, Firebird 5.0.3. Исправленный драйвер сохраняет upstream version 1.4.0: одной версии недостаточно для идентификации сборки. Сохраняйте commit SHA исходников и SHA256 wheel. Публикации пакетов этим процессом нет.

Из общего родительского каталога двух репозиториев:

```sh
git -C pyfirebirdsql rev-parse HEAD
git -C sqlalchemy-firebirdsql rev-parse HEAD
# Оба tracked working tree должны быть чистыми.
uv build pyfirebirdsql --wheel --out-dir sqlalchemy-firebirdsql/baseline/release-wheels
uv build sqlalchemy-firebirdsql --wheel --out-dir sqlalchemy-firebirdsql/baseline/release-wheels
sha256sum sqlalchemy-firebirdsql/baseline/release-wheels/*.whl
uv venv sqlalchemy-firebirdsql/baseline/release-venv --python python3.13
uv pip install --python sqlalchemy-firebirdsql/baseline/release-venv/bin/python \
  sqlalchemy-firebirdsql/baseline/release-wheels/*.whl \
  'sqlalchemy==2.1.4' 'greenlet==3.5.6' 'alembic==1.18.4'
uv pip freeze --python sqlalchemy-firebirdsql/baseline/release-venv/bin/python \
  > sqlalchemy-firebirdsql/baseline/release-installed.txt
```

Для повторного развёртывания сохраняйте сами wheel, их hashes и полный dependency lock/wheelhouse; команды выше фиксируют основные версии, но не все транзитивные зависимости и build backend. Это проверенный путь установки исправленного кода, не обещание byte-for-byte воспроизводимой сборки. Не заменяйте локальный driver wheel одноимённой версией из PyPI.

Проверка выполнялась из `/tmp` в новом venv: импорт из site-packages, async SELECT и engine.dispose на изолированной baseline БД. Секреты и URL передавайте через окружение, не сохраняйте в распространяемых артефактах.

## Alembic (опционально)

Установите extra `sqlalchemy-firebirdsql[alembic]` из своей локальной сборки либо Alembic==1.18.4 отдельно и добавьте в migration `env.py`:

```python
import sqlalchemy_firebirdsql.alembic
```

Для async engine используйте стандартный `await connection.run_sync(do_run_migrations)`. Модуль регистрирует Firebird implementation с transactional DDL. Проверены online create/drop table, add/drop column и rename column, включая rollback добавления столбца. Firebird 5 §5.4.2 использует `ADD name`, `DROP name`, `ALTER COLUMN old TO new`, а не общий Alembic SQL. Rename table, ADD IF NOT EXISTS и DROP IF EXISTS явно отклоняются. Полная поддержка autogenerate, batch migrations, comments, identity alterations и всех constraint/type изменений не сертифицирована.

ORM smoke проверяет AsyncSession CRUD, generated key через явный `Identity()`, savepoint rollback и полный rollback. Для генерируемого PK объявляйте `mapped_column(Identity(), primary_key=True)`: обычный integer PK без явного Identity не создаёт серверный генератор.
