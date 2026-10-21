# sqlalchemy-firebirdsql

Диалект SQLAlchemy для Firebird на основе драйвера `pyfirebirdsql`. Диалект предоставляет синхронный API и асинхронный API.

- [Реализованные функции и оставшиеся работы](docs/implementation-status.ru.md)
- [Ограничения и риски](docs/capabilities.ru.md)
- [Сборка wheel и установка](docs/local-release.ru.md)

## 1. Требования

| Компонент | Требование | Проверенная версия |
|---|---|---|
| Python | >=3.12 | 3.13.5 |
| Firebird | Используйте Firebird 5 для описанных сценариев | 5.0.3 |
| SQLAlchemy | Метаданные пакета допускают >=2.0.41 | 2.1.4 |
| greenlet | Установите для асинхронного API | 3.5.6 |
| Alembic | Установите для миграций | 1.18.4 |

> [!IMPORTANT]
> Используйте диалект с исправленным драйвером `pyfirebirdsql`.
> Проверенные коммиты: диалект `5470363`, драйвер `3258106`.
> Установка `firebirdsql` из PyPI не гарантирует наличие исправлений.
> Фиксируйте commit SHA исходников и SHA256 файлов wheel.

## 2. Установка в проект

### Подготовьте исходники

Используйте следующую структуру каталогов:

```text
workspace/
    pyfirebirdsql/
    sqlalchemy-firebirdsql/
    my-app/
```

| Репозиторий | Адрес | Ветка с проверенными исправлениями |
|---|---|---|
| Драйвер | https://github.com/Soft72tech/pyfirebirdsql | `upstream-missing-fixes` |
| Диалект | https://github.com/Soft72tech/sqlalchemy-firebirdsql | `master` |

Ветки могут содержать новые коммиты. Для воспроизведения проверки используйте коммиты из раздела «Требования».

### Установите через pip

Выполните команды из каталога, содержащего `workspace`.

1. Перейдите в каталог приложения.

   ```sh
   cd workspace/my-app
   ```

2. Создайте виртуальное окружение.

   ```sh
   python3.13 -m venv .venv
   ```

В PowerShell используйте `.venv\Scripts\Activate.ps1` для активации виртуального окружения.

3. Активируйте виртуальное окружение.

   ```sh
   . .venv/bin/activate
   ```

4. Обновите pip.

   ```sh
   python -m pip install --upgrade pip
   ```

5. Установите драйвер, диалект и зависимости асинхронного API.

   ```sh
   python -m pip install \
     -e ../pyfirebirdsql \
     -e ../sqlalchemy-firebirdsql \
     'sqlalchemy[asyncio]==2.1.4' 'greenlet==3.5.6'
   ```

6. Проверьте зависимости.

   ```sh
   python -m pip check
   ```

### Установите через uv

Используйте этот вариант вместо установки через pip. Выполните команды из `workspace/my-app`.

1. Создайте виртуальное окружение.

   ```sh
   uv venv --python 3.13
   ```

2. Установите драйвер, диалект и зависимости асинхронного API.

   ```sh
   uv pip install --python .venv/bin/python \
     -e ../pyfirebirdsql \
     -e ../sqlalchemy-firebirdsql \
     'sqlalchemy[asyncio]==2.1.4' 'greenlet==3.5.6'
   ```

Editable-установка использует исходники из указанных каталогов. Для развёртывания установите wheel драйвера и wheel диалекта. Не заменяйте исправленный драйвер пакетом из PyPI без проверки исходников.

См. [инструкцию сборки wheel](docs/local-release.ru.md).

Установка диалекта регистрирует SQLAlchemy entry points. Не вызывайте `registry.register()` для описанных подключений.

## 3. Запуск Firebird для разработки

Пропустите этот раздел, если сервер Firebird и база данных уже существуют. Установка диалекта не создаёт базу данных.

> [!CAUTION]
> Compose-конфигурация использует пароль `root` и публикует порт 3050 на всех интерфейсах.
> Конфигурация не задаёт постоянный data volume.
> Не используйте её для production или хранения ценных данных.
> Для production настройте постоянное хранилище, резервное копирование, сетевые ограничения и отдельного пользователя приложения.

1. Перейдите в каталог диалекта из каталога, содержащего `workspace`.

   ```sh
   cd workspace/sqlalchemy-firebirdsql
   ```

Следующая команда использует host-порт 3050. При конфликте измените host-порт в `docker-compose.yml` и `FIREBIRD_PORT` приложения.

2. Запустите сервер Firebird.

   ```sh
   docker compose up -d firebird
   ```

3. Откройте журнал сервера Firebird.

   ```sh
   docker compose logs -f firebird
   ```

4. Дождитесь завершения инициализации сервера Firebird.

5. Закройте просмотр журнала сочетанием `Ctrl+C`.

| Параметр | Значение в `docker-compose.yml` |
|---|---|
| Образ | `firebirdsql/firebird:5.0.3` |
| Адрес подключения с хоста | `127.0.0.1:3050` |
| Пользователь | `SYSDBA` |
| Пароль | `root` |
| База данных | `/var/lib/firebird/data/db.fdb` |
| Charset базы данных | `UTF8` |

Образ создаёт базу данных при инициализации. `Ctrl+C` завершает просмотр журнала, но не останавливает сервер Firebird. Из контейнера приложения подключайтесь по доступному имени сервиса и внутреннему порту 3050. `127.0.0.1` внутри контейнера обозначает этот контейнер.

Для остановки сервера Firebird выполните команду:

```sh
docker compose stop firebird
```

> [!CAUTION]
> Не запускайте `task clean`, `task local-tests` или `task tests` для базы данных с нужными данными.
> Эти задачи вызывают `compose down -v` и удаляют volumes.

## 4. Настройки подключения

### Задайте переменные окружения

Следующие реквизиты предназначены только для локального сервера Firebird из раздела 3. Для production передайте пароль через хранилище секретов. Не сохраняйте пароль в исходниках или системе контроля версий.

Задайте переменные окружения в терминале приложения:

```sh
export FIREBIRD_HOST=127.0.0.1
export FIREBIRD_PORT=3050
export FIREBIRD_DATABASE=/var/lib/firebird/data/db.fdb
export FIREBIRD_USER=SYSDBA
export FIREBIRD_PASSWORD=root
```

`FIREBIRD_DATABASE` содержит путь в файловой системе сервера Firebird. Укажите существующую базу данных при подключении к другому серверу Firebird. PowerShell использует синтаксис `$env:FIREBIRD_HOST = "127.0.0.1"` вместо `export`.

### Создайте конфигурацию приложения

Создайте `db_config.py` в каталоге приложения:

```python
import os

from sqlalchemy import URL


def database_url(*, async_: bool = False) -> URL:
    return URL.create(
        "firebird+firebirdsql_async" if async_ else "firebird+firebirdsql",
        username=os.environ["FIREBIRD_USER"],
        password=os.environ["FIREBIRD_PASSWORD"],
        host=os.environ.get("FIREBIRD_HOST", "127.0.0.1"),
        port=int(os.environ.get("FIREBIRD_PORT", "3050")),
        database=os.environ["FIREBIRD_DATABASE"],
        query={"charset": "UTF8"},
    )
```

`URL.create()` принимает пароль без ручного URL-экранирования. Функция `database_url()` использует следующие значения:

| Переменная окружения | Значение по умолчанию |
|---|---|
| `FIREBIRD_HOST` | `127.0.0.1` |
| `FIREBIRD_PORT` | `3050` |
| `FIREBIRD_DATABASE` | Обязательная переменная |
| `FIREBIRD_USER` | Обязательная переменная |
| `FIREBIRD_PASSWORD` | Обязательная переменная |

Функция `database_url()` задаёт charset подключения `UTF8`.

Для строкового URL абсолютный путь базы данных требует двух `/` перед `var`. В примерах ниже указан пароль локального сервера Firebird.

```text
firebird+firebirdsql://SYSDBA:root@127.0.0.1:3050//var/lib/firebird/data/db.fdb
firebird+firebirdsql_async://SYSDBA:root@127.0.0.1:3050//var/lib/firebird/data/db.fdb
```

## 5. Проверка синхронного подключения

1. Создайте `check_sync.py` рядом с `db_config.py`.

   ```python
   from sqlalchemy import Integer, create_engine, literal, select

   from db_config import database_url

   engine = create_engine(database_url(), pool_pre_ping=True)
   try:
       with engine.connect() as connection:
           print(connection.scalar(select(literal(1, Integer))))
   finally:
       engine.dispose()
   ```

2. Запустите проверку.

   ```sh
   python check_sync.py
   ```

Ожидаемый вывод: `1`. Проверка не создаёт таблицы и не изменяет данные.

## 6. Проверка асинхронного подключения

Создавайте один async engine на процесс/event loop приложения. Вызывайте `await engine.dispose()` при завершении приложения. Не передавайте один `AsyncSession` нескольким параллельным задачам.

1. Создайте `check_async.py` рядом с `db_config.py`.

   ```python
   import asyncio

   from sqlalchemy import Integer, literal, select
   from sqlalchemy.ext.asyncio import create_async_engine

   from db_config import database_url


   async def main():
       engine = create_async_engine(database_url(async_=True), pool_pre_ping=True)
       try:
           async with engine.connect() as connection:
               result = await connection.scalar(select(literal(1, Integer)))
               print(result)
       finally:
           await engine.dispose()


   if __name__ == "__main__":
       asyncio.run(main())
   ```

2. Запустите проверку.

   ```sh
   python check_async.py
   ```

Ожидаемый вывод: `1`. Проверка не создаёт таблицы и не изменяет данные.

## 7. Подключение ORM к приложению

> [!CAUTION]
> Следующий пример создаёт таблицу `dialect_demo_items` и добавляет строку при каждом запуске.
> Выполняйте пример только на отдельной базе данных для разработки.

Один `primary_key=True` не гарантирует генерацию первичного ключа. Для генерации ключа задайте `Identity()`. Для изменений через Core используйте `engine.begin()` или явно вызывайте commit. `connect()` не выполняет автоматический commit INSERT, UPDATE или DDL. Считывайте результаты до полного commit/rollback.

1. Создайте `orm_example.py` рядом с `db_config.py`.

   ```python
   import asyncio

   from sqlalchemy import Identity, String, select
   from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
   from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

   from db_config import database_url


   class Base(DeclarativeBase):
       pass


   class Item(Base):
       __tablename__ = "dialect_demo_items"

       id: Mapped[int] = mapped_column(Identity(), primary_key=True)
       name: Mapped[str] = mapped_column(String(100))


   async def main():
       engine = create_async_engine(database_url(async_=True), pool_pre_ping=True)
       sessions = async_sessionmaker(engine, expire_on_commit=False)
       try:
           async with engine.begin() as connection:
               await connection.run_sync(Base.metadata.create_all)

           async with sessions() as session:
               async with session.begin():
                   item = Item(name="example")
                   session.add(item)
                   await session.flush()
                   print("Created:", item.id)

           async with sessions() as session:
               items = await session.scalars(select(Item).order_by(Item.id))
               print([(item.id, item.name) for item in items])
       finally:
           await engine.dispose()


   if __name__ == "__main__":
       asyncio.run(main())
   ```

2. Запустите пример.

   ```sh
   python orm_example.py
   ```

Контекст `session.begin()` выполняет commit при успехе и rollback при исключении. `Identity()` задаёт генерацию первичного ключа сервером Firebird.

Используйте миграции вместо `Base.metadata.create_all` для изменения структуры базы данных production.

## 8. Alembic (опционально)

Проверены online create/drop table, add/drop/rename column и rollback DDL. Полная поддержка autogenerate, batch и всех ALTER-операций не заявлена. Интеграция отклоняет rename table и IF [NOT] EXISTS в поддержанных ALTER API. Проверяйте миграции на отдельной базе данных перед применением.

1. Установите extra `alembic` из каталога приложения.

   ```sh
   python -m pip install -e '../sqlalchemy-firebirdsql[alembic]'
   ```

2. Создайте каталог миграций.

   ```sh
   alembic init -t async migrations
   ```

3. Добавьте `import sqlalchemy_firebirdsql.alembic` в `migrations/env.py`.

4. Импортируйте ORM-модели в `migrations/env.py`.

5. Установите `target_metadata = Base.metadata` в `migrations/env.py`.

Не сохраняйте пароль в `alembic.ini`. Получайте реквизиты через `database_url(async_=True)` из `db_config.py`.

6. Передайте результат `database_url(async_=True)` в создание async engine в `migrations/env.py`.

7. Сохраните вызов `await connection.run_sync(do_run_migrations)` из async-шаблона.

См. [границы поддержки Alembic](docs/local-release.ru.md).

## 9. Тесты диалекта

Выполните команды из `sqlalchemy-firebirdsql` в виртуальном окружении с установленными драйвером и диалектом.

### Запустите проверки без базы данных

1. Установите pytest.

   ```sh
   python -m pip install pytest
   ```

Перед следующей командой удалите `FIREBIRD_TEST_URL` из окружения. При заданной переменной тесты подключаются к указанной базе данных.

2. Запустите проверки.

   ```sh
   PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
     -c /dev/null --noconftest -p no:cacheprovider \
     test/test_bind_casts.py test/test_async_rowcount.py \
     test/test_async_lifecycle.py test/test_time_timezone.py -q
   ```

Pytest пропустит проверки с подключением к базе данных.

### Запустите official suite

> [!CAUTION]
> Suite создаёт и удаляет объекты базы данных.
> Используйте только отдельную базу данных для тестов.
> Не передавайте реквизиты базы данных приложения или production.

Создайте базу данных `dialect_tests.fdb` до запуска suite. Команды ниже не создают базу данных. Примените [CTAS capability guard](docs/patches/README.md) к установленной SQLAlchemy для воспроизведения результата. Без guard два CTAS-теста могут завершиться ошибкой: Firebird 5 не поддерживает CTAS.

1. Задайте URL базы данных для тестов.

   ```sh
   export TEST_DBURI='firebird+firebirdsql://SYSDBA:root@127.0.0.1:3050//var/lib/firebird/data/dialect_tests.fdb'
   ```

2. Запустите синхронный official suite.

   ```sh
   PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
     test/test_official_suite.py --dburi "$TEST_DBURI" --maxfail=0 --tb=short -rs
   ```

3. Замените `firebird+firebirdsql` на `firebird+firebirdsql_async` в `TEST_DBURI`.

4. Повторите команду запуска official suite.

Выполняйте прогоны на одной базе данных последовательно. Для отдельных проверок с подключением задавайте `FIREBIRD_TEST_URL`, а не `TEST_DBURI`.

| Проверка | Последний результат |
|---|---|
| Синхронный official suite | 1042 passed, 495 skipped |
| Асинхронный official suite | 1042 passed, 495 skipped |
| Дополнительная regression-группа | 276 passed |

Результаты относятся к проверенному стеку и [адаптациям suite](docs/implementation-status.ru.md). Они не подтверждают поддержку всех API SQLAlchemy.

## 10. Частые проблемы и ограничения

| Симптом / задача | Действие |
|---|---|
| `NoSuchModuleError` для Firebird | Установите диалект в окружение приложения. Используйте `firebird+firebirdsql` или `firebird+firebirdsql_async` |
| Ошибка greenlet / async bridge | Установите `sqlalchemy[asyncio]`. Используйте engine в его event loop |
| Connection refused | Проверьте завершение инициализации сервера Firebird, адрес, порт и публикацию порта Docker |
| База данных не найдена | Проверьте серверный путь, наличие базы данных и права сервера Firebird |
| Изменения данных не сохраняются | Выполните commit или используйте контекст begin |
| Данные контейнера не сохраняются | Настройте постоянное хранилище перед размещением данных |
| Первичный ключ не генерируется | Добавьте `Identity()` в модель |
| Ошибка TIME с timezone offset | Не используйте fixed-offset TIME binds: драйвер отклоняет их |
| Нужны JSON/ARRAY/streaming/native bulk | Проверьте [статус реализации](docs/implementation-status.ru.md): полноценные API не заявлены |
| Нужен async executemany rowcount | Учитывайте значение -1. Синхронный API поддерживает суммарный счётчик |

Точность времени Firebird — 100 мкс. SQL schemas, CTAS и stored computed не поддерживаются в рассматриваемой версии Firebird. Диалект не переводит SQLAlchemy regexp operators в SIMILAR TO. Полная неблокируемость, нагрузочная устойчивость и все миграционные сценарии не сертифицированы.

См. [сводный отчёт о реализации](docs/implementation-status.ru.md).
