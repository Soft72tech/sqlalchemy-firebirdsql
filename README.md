# sqlalchemy-firebirdsql

Диалект SQLAlchemy для Firebird с синхронным и асинхронным API поверх `pyfirebirdsql`.

- [Что реализовано и что ещё нет](docs/implementation-status.ru.md)
- [Подробные ограничения и практические риски](docs/capabilities.ru.md)
- [Сборка wheel и локальная поставка](docs/local-release.ru.md)

## 1. Требования

- Python **3.12+**; проверки выполнялись на **3.13.5**.
- Firebird **5**; проверен **5.0.3**.
- Проверенная версия SQLAlchemy — **2.1.4**.
- Для async требуется `greenlet`; его устанавливает extra `sqlalchemy[asyncio]`.
- Для разработки нужна актуальная локальная копия **обоих** репозиториев: диалекта и исправленного драйвера.

**Важно:** текущие результаты получены с локальными исправлениями `pyfirebirdsql`, а не с произвольным пакетом из PyPI. Проверенный код: диалект `5470363`, драйвер `3258106`. Исправления могут ещё отсутствовать в удалённом репозитории и опубликованных пакетах. Одного номера версии драйвера недостаточно: сохраняйте commit SHA и артефакты сборки.

## 2. Установка в проект

Предполагается следующая структура каталогов:

```text
workspace/
    pyfirebirdsql/
    sqlalchemy-firebirdsql/
    my-app/
```

В `pyfirebirdsql/` и `sqlalchemy-firebirdsql/` должны находиться исходники с нужными исправлениями. Если требуется получить репозитории, их адреса:

```text
https://github.com/Soft72tech/pyfirebirdsql
https://github.com/Soft72tech/sqlalchemy-firebirdsql
```

Проверьте наличие нужных коммитов после клонирования; отсутствие ещё не опубликованных исправлений нельзя исправить обычным обновлением из PyPI.

Из каталога вашего приложения:

```sh
cd workspace/my-app
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  -e ../pyfirebirdsql \
  -e ../sqlalchemy-firebirdsql \
  'sqlalchemy[asyncio]==2.1.4' 'greenlet==3.5.6'
python -m pip check
```

На Windows активация окружения: `.venv\Scripts\Activate.ps1` в PowerShell. Далее используйте `python` из этого окружения.

Вариант с `uv` вместо `venv`/`pip`:

```sh
uv venv --python 3.13
uv pip install --python .venv/bin/python \
  -e ../pyfirebirdsql \
  -e ../sqlalchemy-firebirdsql \
  'sqlalchemy[asyncio]==2.1.4' 'greenlet==3.5.6'
```

Editable-установка подходит для разработки: приложение использует изменения исходников сразу. Для поставки собирайте и устанавливайте **оба wheel**, а не заменяйте локальный драйвер одноимённой версией из PyPI. Команды и требования к фиксации зависимостей: [локальная поставка](docs/local-release.ru.md).

Отдельно регистрировать диалект через `registry.register()` не нужно: установка пакета добавляет SQLAlchemy entry points. Если пакет не установлен, наличие его каталога рядом с приложением не заменяет регистрацию.

## 3. Запуск Firebird для разработки

Если уже есть подходящий сервер и база, пропустите этот раздел. Установка диалекта сама по себе **не создаёт базу**.

В репозитории есть `docker-compose.yml` с Firebird 5.0.3. Для отдельной локальной разработки:

```sh
cd workspace/sqlalchemy-firebirdsql
docker compose up -d firebird
docker compose logs -f firebird
```

Дождитесь окончания инициализации; `Ctrl+C` завершает просмотр логов, не сервер.

Параметры этого compose-файла:

| Параметр | Значение |
|---|---|
| Адрес с хоста | `127.0.0.1:3050` |
| Администратор | `SYSDBA` |
| Пароль для локальной разработки | `root` |
| База, создаваемая образом при инициализации | `/var/lib/firebird/data/db.fdb` |
| Charset базы | `UTF8` |

**Это dev-конфигурация:** порт в текущем compose публикуется на всех интерфейсах, пароль простой, явный постоянный data volume не настроен. Не используйте её без изменений для production или хранения ценных данных. Для постоянного развёртывания настройте volume, резервное копирование, ограничение сети и отдельного пользователя приложения. Не публикуйте Firebird в интернет.

Если 3050 занят, измените host-порт в compose и `FIREBIRD_PORT` приложения. Не запускайте второй сервер поверх существующего контейнера/каталога данных. Внутри другой Docker-сети адресом будет имя доступного сервиса и его внутренний порт, а не `127.0.0.1` хоста.

Остановить сервер без удаления контейнера:

```sh
docker compose stop firebird
```

Не используйте `task clean`, `task local-tests` или `task tests` для БД с нужными данными: Taskfile выполняет очистку через `compose down -v`. Для тестов нужна отдельная расходная база.

## 4. Настройки подключения

В каталоге приложения задайте переменные окружения; значения ниже относятся только к dev-серверу из предыдущего раздела:

```sh
export FIREBIRD_HOST=127.0.0.1
export FIREBIRD_PORT=3050
export FIREBIRD_DATABASE=/var/lib/firebird/data/db.fdb
export FIREBIRD_USER=SYSDBA
export FIREBIRD_PASSWORD=root
```

Путь базы относится к файловой системе **сервера Firebird**, не Python-приложения. Для существующего сервера используйте его реквизиты и существующую базу. В production пароль храните в секретах окружения, не в исходниках.

Создайте `db_config.py` в своём приложении:

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

`URL.create()` позволяет не экранировать вручную специальные символы в пароле. Эквивалентная строковая форма URL для dev-базы:

```text
firebird+firebirdsql://SYSDBA:root@127.0.0.1:3050//var/lib/firebird/data/db.fdb
firebird+firebirdsql_async://SYSDBA:root@127.0.0.1:3050//var/lib/firebird/data/db.fdb
```

Двойной `/` перед `var` здесь нужен для абсолютного серверного пути.

## 5. Быстрая проверка sync

Создайте `check_sync.py` рядом с `db_config.py`:

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

Запуск:

```sh
python check_sync.py
```

Ожидаемый вывод: `1`. Проверка не создаёт таблиц и не изменяет данные.

## 6. Быстрая проверка async

Создайте `check_async.py`:

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

```sh
python check_async.py
```

Ожидаемый вывод: `1`. `await engine.dispose()` обязателен при завершении приложения. В веб-приложении создавайте engine один раз на процесс/event loop, а закрывайте в shutdown/lifespan, не после каждого запроса. Не используйте один `AsyncSession` параллельно в нескольких задачах.

## 7. Подключение ORM к приложению

Пример `orm_example.py` использует `db_config.py` выше. **Он создаёт demo-таблицу и добавляет строку**, поэтому запускайте его только на предназначенной для этого БД:

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
        # Для demo. В приложении структуру БД меняйте отдельно миграциями.
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

```sh
python orm_example.py
```

Для генерации ключа задавайте **`Identity()` явно**. Один `primary_key=True` не гарантирует создание серверного генератора. Контекст `session.begin()` делает commit при успехе и rollback при исключении. Результаты считывайте до полного завершения транзакции.

Для Core-изменений аналогично используйте `engine.begin()` или `async with engine.begin()`: обычный `connect()` сам по себе не означает автоматический commit ваших INSERT/UPDATE/DDL.

## 8. Alembic (опционально)

В активированном окружении приложения:

```sh
python -m pip install -e '../sqlalchemy-firebirdsql[alembic]'
alembic init -t async migrations
```

В созданном `migrations/env.py`:

- Добавьте `import sqlalchemy_firebirdsql.alembic` для регистрации Firebird implementation.
- Импортируйте свои ORM models и установите `target_metadata = Base.metadata`.
- Передайте URL из `database_url(async_=True)` в создание async engine. Не сохраняйте пароль в `alembic.ini`.
- Сохраните стандартный мост `await connection.run_sync(do_run_migrations)` из async-шаблона.

Проверенный объём: online create/drop table, add/drop/rename column и rollback DDL. **Полная поддержка autogenerate, batch и всех ALTER-операций не заявлена.** Проверяйте SQL и миграции на отдельной БД перед применением. Rename table и IF [NOT] EXISTS в поддержанных ALTER API явно отклоняются.

Подробнее: [Alembic и локальная поставка](docs/local-release.ru.md).

## 9. Тесты диалекта

Тесты запускайте из каталога `sqlalchemy-firebirdsql` в окружении с установленными локальным драйвером, диалектом и pytest:

```sh
python -m pip install pytest
```

Database-free проверки (live cases будут пропущены, если переменная `FIREBIRD_TEST_URL` не задана):

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  -c /dev/null --noconftest -p no:cacheprovider \
  test/test_bind_casts.py test/test_async_rowcount.py \
  test/test_async_lifecycle.py test/test_time_timezone.py -q
```

Для live-регрессий явно задайте `FIREBIRD_TEST_URL` **отдельной тестовой БД**. Они могут создавать/удалять объекты. Никогда не направляйте suite на production или БД приложения.

Полный official suite использует `test/test_official_suite.py`. Некоторые проверки upstream suite требуют локального CTAS guard: [описание и patch](docs/patches/README.md). Без него два неподдерживаемых Firebird CTAS случая могут падать; не считать их поддержкой CTAS или ошибкой драйвера.

```sh
# Только существующая отдельная тестовая БД; подставьте свои реквизиты.
export TEST_DBURI='firebird+firebirdsql://SYSDBA:root@127.0.0.1:3050//var/lib/firebird/data/dialect_tests.fdb'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  test/test_official_suite.py --dburi "$TEST_DBURI" --maxfail=0 --tb=short -rs
```

Для async повторите команду с `firebird+firebirdsql_async`. Прогоны на одной БД выполняйте **последовательно**. База `dialect_tests.fdb` в этом примере автоматически не создаётся.

Последний проверенный результат: sync/async каждый **1042 passed, 495 skipped**; дополнительная regression-группа — **276 passed**. Это результат оговорённого стека с адаптациями suite, не гарантия поддержки всех API SQLAlchemy.

## 10. Частые проблемы и ограничения

| Симптом / задача | Что проверить |
|---|---|
| `NoSuchModuleError` для Firebird | Диалект установлен именно в Python-окружение приложения; URL использует `firebird+firebirdsql` или `firebird+firebirdsql_async` |
| Нет greenlet / async bridge error | Установлен `sqlalchemy[asyncio]`, sync и async API не смешаны, engine работает в своём event loop |
| Connection refused | Сервер завершил инициализацию, адрес/порт верны, Docker-порт свободен; внутри контейнера localhost обозначает сам контейнер |
| База не найдена | База существует, путь правильный на сервере, у Firebird есть права доступа |
| Данные исчезают после выхода | Для записи нужен commit или контекст begin; для контейнера настроено постоянное хранилище |
| Нет автоматически созданного PK | В модели указан `Identity()`, а не только integer primary key |
| Ошибка TIME с timezone offset | Fixed-offset TIME binds пока не поддержаны; общий timezone gate закрыт |
| Нужен JSON/ARRAY/streaming/native bulk | Полноценные API пока не заявлены; см. сводный отчёт, не рассчитывайте на сходство с PostgreSQL |
| Нужен async executemany rowcount | Adapter возвращает -1; sync поддерживает суммарный счётчик |

Другие важные ограничения: точность времени 100 мкс; нет SQL schemas и CTAS; stored computed не поддерживаются; регэкспы SQLAlchemy не подменяются автоматически на SIMILAR TO. Полная неблокируемость, нагрузочная устойчивость и все миграционные сценарии не сертифицированы.

Полная карта готовности: [сводный отчёт](docs/implementation-status.ru.md).
