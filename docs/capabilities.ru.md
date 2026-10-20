# Возможности и ограничения sqlalchemy-firebirdsql

Практическое руководство для разработчиков приложений. Описывает текущую разработку, а не гарантии опубликованного пакета.

Вычисляемые столбцы поддерживают `Computed(..., persisted=False)` и значение по умолчанию `None`; оба создают virtual computed column. Reflection возвращает `persisted=False`. `persisted=True` отклоняется при компиляции: stored computed columns не реализованы сервером. Unit/live DDL, reflection и пересчёт после UPDATE: 8 passed для sync/async.

В SQLAlchemy 2.1 `CreateView(..., or_replace=True)` компилируется в Firebird `CREATE OR ALTER VIEW`, сохраняющий права и зависимости существующего VIEW (§5.6.3). Официальная view-группа: sync/async по 8 passed, 23 skipped; 4 unit-проверки DDL. Это не поддержка materialized/temporary views.

## 1. Границы проверки

Проверенный стек: **Python 3.13.5, SQLAlchemy 2.1.4, Firebird 5.0.3**, локальный `pyfirebirdsql` версии 1.4.0 с исправлениями до `a642c49`; диалект с temporal RANGE, bitwise, autocommit detection, national string DDL и row-at-a-time INSERT RETURNING fallback. Метаданные проекта допускают Python >=3.12 и SQLAlchemy >=2.0.41, но это не означает, что все эти сочетания проверены.

**Важно о зависимостях:** результаты получены с локально исправленным драйвером. Обычная установка `firebirdsql>=1.4.0` не гарантирует наличие этих исправлений. Для воспроизведения нужен соответствующий исходный код; публикация исправленной версии и установка из PyPI отдельно не проверялись.

Актуальный полный SQLAlchemy official suite для каждого sync/async: **1021 passed, 495 skipped, 0 failures/errors**. Применён явный [upstream CTAS capability patch](patches/README.md): два неподдерживаемых CTAS случая теперь пропускаются по существующему requirement; это не исправление драйвера и не поддержка CTAS. UNION branches с pagination оборачиваются в derived table для допустимого использования ROWS (Firebird 5 §6.1.9); открыты три compound-select gates, official CompoundSelectTest — по 7 passed. Дополнительные регрессии `test_compound_pagination.py`: 19 passed, включая sync/async cached rebinding, expression limit, offset-only, FETCH и result keys. Дополнительные новые регрессионные проверки драйвера и диалекта: **180 passed** (включая live temporal RANGE, bitwise, national strings, table options и RETURNING fallback). Это не сертификация всех ORM-сценариев, миграций, производительности или отказоустойчивости.

В таблицах:

- **Нативно** — операцию выполняет Firebird; диалект переводит SQLAlchemy в его SQL.
- **Адаптация** — диалект/драйвер преобразует типы, SQL или вызовы API; это не новая функция сервера.
- **Эмуляция** — поведение заменено другой моделью хранения или операциями.
- **Не поддерживается** — нет рабочего контракта в текущем стеке. Причина может быть в сервере либо библиотеке.
- **Не подтверждено** — текущие результаты не дают основания обещать поддержку.

## 2. Подключение и asyncio

| Возможность | Реализация | Что учитывать |
|---|---|---|
| Sync engine | Диалект поверх `firebirdsql` | URL `firebird+firebirdsql` |
| Async engine | `firebirdsql.aio` через адаптер SQLAlchemy и greenlet-мост | Это не запуск всего sync-драйвера в thread pool; для async нужен greenlet |
| Commit, rollback, savepoints, autocommit | Серверные транзакции плюс адаптация lifecycle | Не заменяют прикладную стратегию повторов при конфликтах |
| Pool ping | В async адаптер await-ит ping; переподключение оставлено pool | Поведение при длительном обрыве сети отдельно не сертифицировано |
| Server-side streaming API | Не заявлено: async `supports_server_side_cursors=False` | Не рассчитывать на `AsyncConnection.stream()` как на поддержанный режим |
| Полностью неблокирующий event loop | **Не подтверждено** | Закрытие соединения синхронное. Обычный SQLAlchemy async cursor получает rowcount через await и кеширует его; raw driver `rowcount` остаётся синхронным (использовать `await cursor.get_rowcount()`) |

Опция SQLAlchemy `skip_autocommit_rollback=True` поддержана: диалект проверяет локальный autocommit flag без сетевого запроса и пропускает rollback только при включённом AUTOCOMMIT. Обычные транзакции по-прежнему откатываются; опция не означает автоматического commit обычных транзакций. Official AutocommitIsolationTest: sync/async по **11 passed**, unit detection/proxy/adapter/rollback: **24 passed**.

Пример подключения к уже существующей БД, без создания схемы:

```python
import asyncio
from sqlalchemy import URL, Integer, bindparam, select
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    url = URL.create(
        "firebird+firebirdsql_async",
        username="app_user", password="replace_me",
        host="127.0.0.1", port=3050,
        database="/var/lib/firebird/data/app.fdb",
    )
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            statement = select(bindparam("value", type_=Integer))
            result = await connection.execute(statement, {"value": 1})
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()

asyncio.run(main())
```

Для sync: `create_engine()` с `firebird+firebirdsql`, обычные `with`, без `await`. Путь БД относится к серверу Firebird, а не к файловой системе клиента. Для async поддержан и выбор async-класса через `create_async_engine()` с `firebird+firebirdsql`.

**Риск asyncio:** успешный suite не доказывает отсутствие блокировок event loop. Для обычного SQLAlchemy async cursor чтение ответа rowcount переведено на await и выполняется до закрытия курсора; свойство результата читает кеш без сети. Для executemany возвращается -1 (итог пакета неизвестен). Это не сертификация всего транспорта: особенно внимательно проверять задержки при закрытии, таймаутах и обрывах сети. Профиль latency, cancellation и многоконкурентную нагрузку нужно проверять на приложении отдельно.

## 3. Типы данных и скрытые преобразования

| Тип/операция | Реализация | Ограничение или рекомендация |
|---|---|---|
| Integer, BigInteger | Нативные целые; параметры получают CAST | В параметризованном SQLAlchemy-выражении сервер узнаёт тип заранее |
| INT128 | Нативный тип; драйвер декодирует 128 бит | Исправленный decoder необходим для значений с установленным старшим битом младшего 64-битного слова |
| Numeric(p, s), Decimal | Нативные exact numerics; типизированные параметры | Для денег и фиксированного масштаба задавать p и s явно |
| Numeric без precision/scale в bind | Адаптация к DECFLOAT(34) | Не обещает произвольную точность Python Decimal; до 34 значащих десятичных цифр |
| Numeric со scale без precision в bind | CAST к NUMERIC(38, scale) | Выбранный scale влияет на диапазон целой части |
| Float() без precision, Double() | DOUBLE PRECISION | Новый DDL использует 64-bit float; уже существующие 32-bit столбцы автоматически не мигрируются |
| Float(p), REAL | FLOAT(p), REAL | В Firebird 5 p — двоичная точность; REAL остаётся single precision |
| String(n), VARCHAR(n) | Нативный VARCHAR; string binds приводятся к text BLOB | Это предотвращает усечение LIKE-паттерна до длины столбца. План и скорость сравнения с BLOB нужно проверять отдельно |
| String без длины | DDL подставляет 255 | Это **не** неограниченная строка; задавать длину либо Text |
| NCHAR, NVARCHAR | NCHAR / NATIONAL CHARACTER VARYING | Firebird national types используют **ISO8859_1**, не произвольный Unicode; для Unicode выбирать String/Text с подходящим charset БД. Длина/reflection и Latin-1 round-trip проверены sync/async |
| Text, UnicodeText, CLOB | Нативный BLOB SUB_TYPE TEXT | Длина Text(255) не ограничивает BLOB до 255 символов |
| Date/Time/DateTime | Нативные типы плюс bind casts | Точность времени Firebird — 100 мкс, не произвольные микросекунды Python |
| DateTime(timezone=True) | TIMESTAMP WITH TIME ZONE | Проверенные temporal-тесты проходят; правила зон зависят и от сервера |
| Time(timezone=True) | DDL умеет WITH TIME ZONE; общий time-zone test закрыт requirements | Не считать произвольные timezone-aware time полностью проверенными |
| Enum | Ненативный SQLAlchemy Enum поверх строк | Серверного ENUM нет; ограничения и validation задавать явно |
| JSON, ARRAY | Полноценная поддержка **не заявлена** | JSON/ARRAY компилируются в BLOB; ARRAY содержит JSON-сериализацию. Это не нативный SQL ARRAY и не JSON query API |
| UUID, Interval | Нативный UUID/полный timedelta-контракт не заявлены | При необходимости явно выбрать прикладное хранение/TypeDecorator и отдельно проверить round-trip |

**Важно для больших Decimal:** дополнительно исправлен Decimal bind в локальном драйвере. Ранее коэффициент без проверки упаковывался в 64 бита и молча усекался: NUMERIC(38,12) мог возвращать неверные значения, включая отрицательные. Теперь коэффициенты вне signed INT64 или scale вне signed byte передаются точным decimal text; сервер преобразует их к целевому типу. Native isql и строковый bind подтвердили отсутствие ошибки хранения/чтения в проверенном случае. Numeric/TrueDiv с временно открытыми четырьмя precision gates: по **40 passed** sync/async. Это дополнительное локальное исправление драйвера, не гарантия опубликованного пакета; произвольная точность и произвольные Decimal special values не заявляются.

### Decimal и деление

Оператор `/` в SQLAlchemy компилируется с повышением обоих операндов: обычно к **DECFLOAT(34)**, для float-левого операнда — к **DOUBLE PRECISION**. Это исключает целочисленное усечение и ошибочный CAST делителя к NUMERIC со scale=0. Но это не произвольная 38-значная точность результата деления.

Для exact Numeric/Decimal с precision >34 чистый числовой `literal_column` внутри CAST передаётся как точный десятичный текст. Это проверенный обход ошибки вложенного числового литерала Firebird 5.0.3, без binary float. Обычные SQL-выражения и raw SQL так не переписываются.

```python
from decimal import Decimal
from sqlalchemy import Numeric, literal, select

statement = select(literal(Decimal("15.7563"), Numeric(18, 4)))
```

**Raw SQL:** автоматические casts относятся к типизированным выражениям SQLAlchemy. Они не добавляются произвольно внутрь `exec_driver_sql()` или строки `text()`. Для неопределяемых параметров используйте `CAST(:value AS INTEGER)` либо `text(...).bindparams(bindparam(..., type_=...))`.

## 4. Запросы и изменение данных

| Возможность | Реализация | Граница поддержки |
|---|---|---|
| SELECT, JOIN, подзапросы, EXISTS, обычный IN | Нативный SQL и компиляция диалекта | Непустые и пустые наборы проверяются suite; tuple IN отдельно не заявлен |
| LIMIT/OFFSET, обычный fetch | Адаптация к ROWS | Для предсказуемой пагинации задавать ORDER BY; PERCENT/WITH TIES не заявлены |
| UNION и ORDER BY | Нативный UNION; диалект заменяет подходящие ссылки на ordinal positions | Не все комбинации вложенных UNION с LIMIT/OFFSET включены в проверку |
| Регулярные выражения | Нативный SQL `SIMILAR TO` через явное SQL-выражение | Это полное совпадение с SQL-pattern, не regexp search: `%`/`_` — wildcards, точка — обычный символ. SQLAlchemy `regexp_match`/`regexp_replace` явно дают CompileError; автоматического перевода нет. Sync/async семантика проверена отдельно |
| CTE, оконные функции | Серверный SQL | RANGE для integer/numeric и temporal ordering проверен; некоторые CTE/DML-варианты закрыты requirements |
| INSERT/UPDATE/DELETE RETURNING | Нативный RETURNING | Singleton BLOB outputs материализуются драйвером как bytes/text, не blob ID |
| Executemany | Путь драйвера; в текущем aio — последовательные execute | Не обещает один сетевой запрос/пакет или ускоренный batch |
| INSERT с несколькими наборами параметров и RETURNING | Адаптация: SQLAlchemy row-at-a-time insertmanyvalues fallback | Один INSERT на строку, результаты собираются SQLAlchemy; порядок по `sort_by_parameter_order=True`, generated keys/return_defaults и rollback проверены. Это не native bulk executemany драйвера |
| Native multi-VALUES INSERT / пакетная insertmanyvalues-вставка | Не поддержаны | `supports_multivalues_insert=False`; оптимизацию числа сетевых round trips не обещаем |
| INSERT INTO ... SELECT | Нативно | Целевая таблица должна уже существовать |
| UPDATE FROM, DELETE USING, two-phase API | Не заявлены текущим диалектом | Не делать вывод о всех возможностях Firebird только из отключённого API suite |

Получать сгенерированные ключи следует через RETURNING/механизмы SQLAlchemy, а не рассчитывать на DBAPI lastrowid. Суммарный достоверный rowcount для executemany не заявлен. Считывайте нужные результаты **до полного commit/rollback**: драйвер освобождает statements курсоров, чтобы они не удерживали metadata locks. Retaining и rollback к savepoint отличаются от полного завершения транзакции.

## 5. Транзакции и DDL

Обычное подключение не переводится принудительно в autocommit. Для явной транзакции используйте `engine.begin()`; для savepoint — `connection.begin_nested()`. В async эти операции await-ятся через API SQLAlchemy.

Диалект принимает `READ COMMITTED`, `READ COMMITTED LEGACY`, `REPEATABLE READ`, `SNAPSHOT`, `SERIALIZABLE`, `AUTOCOMMIT`. `SNAPSHOT` и `REPEATABLE READ` используют одно значение драйвера. Это отображение на режимы Firebird, а не обещание идентичной семантики с одноимёнными режимами других СУБД. Проверки autocommit не заменяют тесты конфликтов двух параллельных транзакций.

**Production DDL не получает автоматический commit из тестового suite.** Его helper из `provision.py` используется при тестировании и подтверждает DDL между операциями. В приложении самостоятельно завершайте DDL-транзакцию, закрывайте результаты и учитывайте metadata locks; нельзя переносить test-only helper в обычное управление транзакциями.

Для async DDL используйте обычный мост SQLAlchemy:

```python
async with engine.begin() as connection:
    await connection.run_sync(metadata.create_all)
# После выхода — явная граница транзакции перед дальнейшей работой.
```

Этот фрагмент предполагает уже созданные `engine` и `metadata`; production-миграции/Alembic отдельно не сертифицированы.

## 6. Структура БД, индексы и reflection

| Возможность | Реализация | Ограничение |
|---|---|---|
| Identity | GENERATED ALWAYS/BY DEFAULT AS IDENTITY | Поддерживаются start/increment; minvalue/maxvalue/cycle/cache компилятор не реализует, не рассчитывать на них |
| Sequence | Нативный NEXT VALUE FOR | Учитывается серверный INCREMENT; проверены наличие, список и прямое получение значения |
| Computed column | Серверное вычисление | Использовать Computed(...), без persisted=True/False; явный persisted вызывает CompileError |
| PK, UNIQUE, FK, CHECK | Серверные ограничения и reflection | UNIQUE/FK имеют backing indexes; нельзя ожидать список только явно созданных indexes |
| Индексы выражений | COMPUTED BY | Несколько expression operands компилятор объединяет через `||`, это не независимые ключи многоколоночного индекса; различие важно для uniqueness и коллизий |
| Смешанные колонки/выражения индекса | Специальная компиляция и reflection | Не обещать произвольную форму: выбор ветки зависит от первого выражения, reflection делит source по `||`; сложные выражения с конкатенацией требуют отдельной проверки |
| Descending/partial index | В коде есть генерация DESCENDING/WHERE | Прикладные dialect options и корректность конкретного DDL проверять отдельно; не считать наличие ветки полным публичным контрактом |
| Reflection | Системные таблицы RDB$, нормализация имён | Проверены столбцы, PK/FK/UNIQUE/CHECK, индексы, identity/computed, views, comments и sequences в включённых вариантах suite |
| get_multi_* | Контракт SQLAlchemy, в том числе общие fallback-механизмы | Нельзя обещать один оптимизированный запрос вместо обхода объектов |
| Отдельные SQL schemas | Не поддерживаются в Firebird 5 / supports_schemas=False | Не задавать schema="test_schema" как в PostgreSQL; schema_translate_map не создаёт schemas |
| Reflection table options | `firebird_on_commit` для GTT; `{}` для обычных таблиц/views | PRESERVE/DELETE ROWS определяются по RDB$RELATION_TYPE; это не полное восстановление SQL SECURITY, external-file и остальных параметров. При пересоздании GTT нужен явный GLOBAL TEMPORARY prefix |

### Что может удивить

- Максимальный ключ индекса зависит от размера страницы: приблизительно четверть страницы с дополнительными ограничениями строк/charset. На тестовой БД страница 4096 байт. Длинное выражение SQL и допустимая ширина результата — разные вещи.
- Превышение ключа теперь вызывает исключение драйвера, а не скрывается. После неудачного DDL нужен rollback; отсутствие индекса нельзя считать успешным созданием.
- В проверенной БД два UNIQUE на одном наборе колонок в разном порядке отвергаются. Не создавайте такие дубликаты при переносе моделей.
- UNIQUE backing index получает `duplicates_constraint`: reflection не должна создавать индекс повторно поверх ограничения. FK-index остаётся видимым.
- Используйте `Identity()` явно. Отдельная ветка `primary_key=True, autoincrement=True` в компиляторе жёстко формирует INTEGER identity; это риск, если ожидается BIGINT или иной тип PK.
- Идентификаторы ограничены 63 символами; нормализация обычных имён и quoted case-sensitive имён различается. При переносе чужих схем проверяйте кавычки.
- Параметры `charset` в собственных string-классах пока нельзя считать универсальным работающим контрактом: некоторые конструкторы присваивают фиксированное значение. Charset подключения, БД и фактический DDL проверять явно.

### CTAS — отдельное ограничение сервера

Firebird 5 не поддерживает `CREATE TABLE ... AS SELECT`. Это создание новой физической таблицы из результата запроса, а не CREATE VIEW. Поддерживаемый путь: **явный CREATE TABLE, затем INSERT INTO ... SELECT**, с корректными транзакционными границами. Автоматической CTAS-эмуляции в диалекте нет.

Два оставшихся failures `TableViaSelectTest.test_without_metadata[plain0/plain1]` — отсутствие capability guard в общем suite, хотя `requires.create_table_as` закрыт. Это не ошибка sync/async протокола. Не объявляем suite зелёным и не отключаем эти два случая ради результата.

Дополнительная проверка reflection: порядок колонок составного индекса и NCHAR/NVARCHAR длины проходят official suite — по **7 passed** sync/async. NVARCHAR DDL исправлен на поддерживаемый `NATIONAL CHARACTER VARYING(n)`; отдельные unit/live регрессии — **7 passed**. Per-column ASC/DESC и repeated-local-column FK этим не объявляются поддержанными.

## 7. Почему 555 skipped — не 555 реализованных возможностей

Исходный полный async-прогон с `-rs`, до исправлений и открытия gates, подтвердил **902 passed, 555 skipped, 2 failed**. Ниже приведён исторический разбор этих 555 skips; актуальный полный результат после изменений — **1017 passed, 497 skipped, 2 failed** для каждого sync/async. Большое число пропусков обусловлено параметризацией и capability gates, но **каждая пропущенная проверка остаётся непроверенной**.

| Группа | Число пропусков | Интерпретация |
|---|---:|---|
| ComponentReflectionTest | 405 | Много сочетаний schema, kind/scope/filter и непредоставляемых reflection API, а не 405 отдельных функций |
| ComponentReflectionTestExtra | 22 | Дополнительные неподходящие варианты reflection |
| TableViaSelectTest | 22 | CTAS/SELECT INTO, materialized/temp views и schema-варианты |
| CTETest | 11 | Неподдержанные/не заявленные формы CTE |
| ExpandingBoundInTest | 11 | В основном tuple IN-варианты |
| Остальные классы | 84 | Типы, precision, DDL, RETURNING, schemas и другие capability gates |
| **Всего** | **555** | Это не число прошедших тестов и не доказательство поддержки исключённых случаев |

Внутри первой группы один `test_multi_get_table_options_tables` даёт **84** пропуска; каждый из семи семейств multi-reflection (columns, PK, FK, indexes, UNIQUE, CHECK, comments) — по **42**. Именно поэтому числа не следует превращать в процент поддержанных функций.

Сам `-rs` выводит 334 причины как `custom function`, 219 как `marked as skip`, по одной — executemany RETURNING и optional sequence. Эти общие сообщения не позволяют автоматически разделить все пропуски на «сервер не умеет» и «ещё не реализовали»; необходима сверка requirements и decorators.

**Два принципиально разных класса:**

1. Неприменимость/ограничение: schemas, materialized views, tuple IN, некоторые DDL-формы; optional sequence не означает отсутствия обычных sequences.
2. Неполная реализация или покрытие: server-side cursors, native bulk RETURNING (не путать с реализованным row-at-a-time fallback), JSON/ARRAY API, numeric precision/timezone/historic-варианты. Часть gates консервативна либо унаследована; комментарий requirements не является проверенным дефектом текущего драйвера.

Например, оконные функции в Firebird есть, но исходный baseline исключал RANGE-тесты (теперь они открыты); DateTime timezone проверяется, а общий Time timezone gate остаётся закрыт. Нельзя переносить статус всего класса на каждую его возможность. Исторические даты и все комбинации precision требуют отдельной проверки перед использованием.

### Точечный аудит закрытых gates

Диагностические прогоны **до исправления Decimal bind** с временным открытием выбранных requirements, без изменения штатных gates: **для каждого sync/async 30 passed, 8 skipped, 2 failed, 1419 deselected**. Это не новый полный suite и не замена baseline. Среди passed — **22 ранее пропускавшихся случая**, остальные 8 — уже открытые варианты деления.

| Закрытый gate / сценарий | Результат sync и async | Вывод |
|---|---|---|
| inline CHECK reflection | 8 passed | Gate унаследован закрытым; проверенные inline/mixed варианты работают |
| server_defaults | 4 passed; 3 expression-варианта остаются skipped | Literal/boolean/current timestamp не отсутствуют; expression defaults — отдельный gate |
| column_collation_reflection | 1 passed | Проверенный collation отражается; gate консервативен |
| duplicate_key_raises_integrity_error | 1 passed | Комментарий requirements об отсутствии IntegrityError устарел для проверенного драйвера |
| precision_generic_float_type, literal_float_coercion | 2 passed | Старые комментарии про single precision не описывают текущие Float()/bind casts |
| precision_numerics_retains_significant_digits | 1 passed | Проверенный Decimal `1.000` сохраняет scale |
| precision_numerics_many_significant_digits | 1 failed; 2 TrueDiv-варианта passed | Общий gate скрывает и рабочие случаи, и реальную ошибку NUMERIC(38,12), описанную выше |
| window_range, window_range_numeric | 2 passed | Firebird 5 поддерживает RANGE; проверенные integer/numeric frames работают |
| window_range_non_numeric | 1 failed до исправления | timedelta ошибочно компилировался в TIMESTAMP-offset; исправлено преобразованием к числовому offset (см. ниже) |
| supports_bitwise_xor | 1 passed | Компилятор уже переводит XOR в BIN_XOR; остальные 5 bitwise-вариантов в этой проверке не открывали |

Firebird 5 reference §10.4 описывает RANGE для numeric/date/time/timestamp ORDER BY; §8.6 — BIN_* функции; §5.6.3 — CREATE OR ALTER VIEW, не тождественный SQLAlchemy CREATE OR REPLACE VIEW. Наличие серверного аналога не гарантирует готовность соответствующего API диалекта.

Главный массовый skip — schema-параметризация: семь multi-reflection семейств пропускают именно по 42 schema-варианта (3 scope × 7 kind × 2 filter); это не отсутствие get_multi_* целиком. Отдельные 84 пропуска table-options закрыты `reflect_table_options`; возможный schema gate здесь перекрывается более ранним исключением. Поэтому непересекающееся распределение всех 555 на сервер/диалект нельзя получить простым сложением закрытых requirements.

В диагностической фазе штатные requirements не менялись. Ошибка exact numeric затем локализована и исправлена в драйвере (см. раздел типов). Unit encoding/INT128/status-vector: **8 passed**. Полный повторный suite после исправления: sync/async по **902 passed, 555 skipped, 2 CTAS failed**. Затем исправлен и temporal RANGE: SQLAlchemy 2.1 FrameClause с timedelta для DATE/TIMESTAMP переводится в дни, для TIME — в секунды через NUMERIC(38,18). Конвертация выполняется при каждом execute, в том числе из statement cache; исходный statement не меняется. DATE требует целых дней, отрицательные magnitude отклоняются. Это адаптация window frame, не универсальная реализация Interval. Live-регрессии проверяют DATE/TIMESTAMP/TIME и повторное выполнение с другим offset, sync/async: **24 passed** вместе с unit-проверками; official WindowFunctionTest с открытыми RANGE gates — по **5 passed**. Теперь открыты 12 проверенных gates: три RANGE, четыре precision, inline CHECK, server defaults, collation reflection, IntegrityError и XOR. Это вернуло **24** проверки без добавления skip/xfail: полный suite sync/async — по **926 passed, 531 skipped, 2 CTAS failed**. Затем добавлены переводы AND/OR/NOT/left shift/right shift в BIN_AND/BIN_OR/BIN_NOT/BIN_SHL/BIN_SHR и открыты остальные bitwise gates. Проверены отрицательные BIGINT (включая arithmetic right shift), NULL и большие 64-bit значения: **20 unit/live passed**, official BitwiseTest — по **6 passed** sync/async. Итог полного suite — по **931 passed, 526 skipped, 2 CTAS failed**. Это серверная fixed-width арифметика, не неограниченные целые Python; переполнение и крайние shift counts не обещаются. Expression defaults остаются закрыты; schema/table-options пропуски этими изменениями не устранялись.

### Почему после продолжения число skips выросло

Открытие `autoincrement_insert` дополнительно допустило к collection весь ReturningTest: **57** прежде не собиравшихся случаев. Сравнивать только 540 skips с прежними 526 некорректно: total вырос с 1459 до 1516. Проверки autocommit, index column order, national strings, identity INSERT и RETURNING дали **+43 passed**; закрытые capability gates новых параметризаций дали net **+14 skipped**. Новых skip/xfail для сокрытия ошибок не добавляли.

При временном открытии autoincrement gate обнаружились 14 failures: executemany RETURNING был запрещён, затем row-at-a-time pipeline выявил два BLOB-output дефекта. Теперь они исправлены; Returning/InsertBehavior/Enum группа даёт sync/async по **50 passed, 26 skipped**. Native multi-VALUES/JSON/UUID-варианты этим не объявлены реализованными.

После реализации `get_table_options` и открытия соответствующего gate вернулись ещё **43** проверки: **1017 passed, 497 skipped, 2 CTAS failed**, всего 1516. Table-options/missing-table группа: по **54 passed, 44 skipped** sync/async; 12 unit/live регрессий проверяют GTT scope, quoted names, single/multi reflection и отсутствие таблицы. Schema-варианты не эмулировались. Оставшиеся 497 skips включают 361 ComponentReflectionTest, 26 ReturningTest и 110 прочих; generic причины pytest всё ещё не дают полного распределения «сервер/диалект».

Дополнительная диагностика repeated FK: Firebird 5 отверг `FOREIGN KEY(cid, cid)` при CREATE TABLE; четыре соответствующих теста не следует открывать как поддерживаемые. Remote-repeat варианты используют ту же отклоняемую local-repeat fixture, поэтому их самостоятельная поддержка этой диагностикой не определена. Expression defaults, per-column ASC/DESC и прочие закрытые возможности требуют отдельной сверки reference и API.

## 8. Что проверено тестами, но не является production-функцией

В `test/test_official_suite.py` находятся явные адаптации фикстур:

- schema-aware fixture использует default namespace, если schemas не поддерживаются;
- ожидания индексов содержат реальный дополнительный FK-index, сравниваются структурно без скрытия индексов;
- длинный source expression сохранён, но результат индексируемого выражения ограничен VARCHAR(100) под key limit страницы;
- два UNIQUE fixture используют разные наборы колонок вместо запрещённых дубликатов;
- identity reflection проверяет реальные always/start/increment, не выдумывая остальные SQL-standard options.

Следовательно, результат относится к **official suite с этими локальными адаптациями**, а не к неизменённому upstream suite. Test-only DDL commit hook также не является возможностью runtime. Ни эти фикстуры, ни закрытые requirements не добавляют отсутствующие функции в Firebird.

## 9. Как проверить свой сценарий

Перед внедрением: закрепить версии/коммиты драйвера, проверить типы и точность на своих данных, планы строковых сравнений, bulk-производительность, транзакционные конфликты, event-loop latency и закрытие соединений при отказах. ORM, Alembic autogenerate, cross-version совместимость и production-нагрузка не покрываются одним итогом Core-oriented suite.

Официальный suite запускался явно, не весь набор файлов проекта:

```sh
# Из корня репозитория, в подготовленном тестовом окружении.
# DBURI должен указывать только на отдельную тестовую БД.
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest test/test_official_suite.py \
  --dburi "$DBURI" --maxfail=0 --tb=short -rs
```

Тесты создают и удаляют объекты БД. Не запускать на production. Прогоны выполнялись последовательно, не одновременно на одной БД. Старый `test/test_suite.py` не является использованным official entry point.

## 10. Основания и дальнейшие проверки

Код: [base.py](../sqlalchemy_firebirdsql/base.py), [compiler.py](../sqlalchemy_firebirdsql/compiler.py), [ddl_compiler.py](../sqlalchemy_firebirdsql/ddl_compiler.py), [firebirdsql.py](../sqlalchemy_firebirdsql/firebirdsql.py), [types.py](../sqlalchemy_firebirdsql/types.py). Requirements задают отбор тестов, но не заменяют код и серверную документацию.

Регрессии: [bind casts](../test/test_bind_casts.py), [numeric](../test/test_numeric_casts.py), [float](../test/test_float_casts.py), [string](../test/test_string_casts.py), [text](../test/test_text_types.py), [sequences](../test/test_sequences.py), [ping](../test/test_async_ping.py), [адаптированный official suite](../test/test_official_suite.py).

Серверная документация: [Firebird 5 Language Reference](https://www.firebirdsql.org/file/documentation/chunk/en/refdocs/fblangref50/firebird-50-language-reference.html), [CREATE TABLE](https://www.firebirdsql.org/file/documentation/chunk/en/refdocs/fblangref50/fblangref50-ddl-table.html), [INSERT](https://www.firebirdsql.org/file/documentation/chunk/en/refdocs/fblangref50/fblangref50-dml-insert.html). Существенные разделы: типы/точность, text BLOB operations, CAST parameters, identity, размер ключа индекса, транзакции и системные таблицы.

Артефакты локального аудита не входят в поставку: `baseline/phase-exact-final-{firebirdsql,firebirdsql_async}.log`, `baseline/phase-report-skips-async.log`, `baseline/phase-open-gates-full-{firebirdsql,firebirdsql_async}.log`, `baseline/phase-bitwise-full-{firebirdsql,firebirdsql_async}.log`, `baseline/phase-returning-enabled-full-{firebirdsql,firebirdsql_async}.log`, `baseline/phase-table-options-full-{firebirdsql,firebirdsql_async}.log`. Полнота неблокирующего asyncio, нагрузочная устойчивость, восстановление после сетевых отказов, все варианты complex expression indexes и пропущенные precision/temporal-проверки остаются отдельными задачами, а не подтверждёнными возможностями.
