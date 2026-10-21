# Сводный отчёт о реализации диалекта Firebird

## 1. Состояние и границы отчёта

Отчёт описывает текущие исходники **sqlalchemy-firebirdsql**, а не гарантии опубликованной версии пакета.

- Диалект: коммит **5470363**.
- Драйвер pyfirebirdsql: коммит **3258106** с необходимыми локальными исправлениями.
- Проверенный стек: Python 3.13.5, SQLAlchemy 2.1.4, Firebird 5.0.3.
- Полный official suite, отдельно sync и async: **1042 passed, 495 skipped, 0 failures/errors** в каждом режиме.
- Дополнительная группа регрессий диалекта и драйвера: **276 passed**.

Suite запускается с документированными адаптациями фикстур и локальным upstream CTAS capability guard. Это не неизменённый upstream suite. Пропуски не означают ни поддержку функций, ни 495 отдельных недоработок: число включает параметризации и неприменимые серверу сценарии. Процент реализованных функций по этим числам вычислять нельзя.

Статусы ниже различают готовую реализацию, частичную поддержку, отсутствие реализации и отсутствие достаточной проверки. Нативную операцию выполняет Firebird; задача диалекта — корректно представить её через SQLAlchemy.

## 2. Реализовано и проверено в указанных границах

| Область | Что реализовано в диалекте | Существенные границы |
|---|---|---|
| Синхронное подключение | SQLAlchemy engine поверх pyfirebirdsql, URL `firebird+firebirdsql` | Зависит от исправленного драйвера |
| Асинхронное подключение | Async engine через firebirdsql.aio и SQLAlchemy adapter; URL `firebird+firebirdsql_async` | Это не перенос всего sync-драйвера в thread pool; полная неблокируемость не сертифицирована |
| Транзакции | Commit, rollback, savepoints, autocommit; обычное подключение не принуждается к autocommit | Проверки конфликтов и всех isolation aliases не завершены |
| Autocommit rollback | Опция `skip_autocommit_rollback=True`, определение режима без сетевого запроса | Пропуск rollback только для AUTOCOMMIT и только по явной опции |
| Async lifecycle | Awaitable закрытие, ping, invalidation/terminate; получение исходного raw async connection | Проверены receive cancellation/timeout/EOF и отдельные сценарии восстановления SQLAlchemy pool |
| Основные запросы | SELECT, JOIN, подзапросы, EXISTS, обычный IN, включая пустые наборы | Не универсальная поддержка всех SQL-конструкций |
| Пагинация | LIMIT/OFFSET и обычный FETCH через ROWS | PERCENT/WITH TIES не поддержаны |
| UNION | Компиляция ORDER BY; branches с пагинацией адаптируются через derived table | Проверены в том числе offset-only, expression limits и cached rebinding |
| Оконные функции | Проверенные оконные выражения; RANGE с integer/numeric и temporal ordering | timedelta преобразуется в дни для DATE/TIMESTAMP, секунды для TIME; DATE требует целые дни |
| Побитовые операции | AND, OR, XOR, NOT, сдвиги через Firebird BIN_* | Серверная fixed-width арифметика, не неограниченные Python integers |
| Изменение данных | INSERT, UPDATE, DELETE, INSERT INTO SELECT, нативный RETURNING | INSERT INTO SELECT требует существующую таблицу |
| Многострочный INSERT с RETURNING | SQLAlchemy row-at-a-time fallback, generated keys, порядок результатов, rollback | Отдельный INSERT на строку; это не native bulk |
| Rowcount | Обычный DML; суммарный executemany rowcount для sync | Async executemany сообщает -1; async result rowcount читается из кеша без wire I/O |
| Числовые типы | Integer/BigInteger, Numeric/Decimal, Float/Double/REAL и типизированные bind casts | Некоторые вычисления адаптируются через DECFLOAT(34), не произвольную точность Decimal |
| Строки и BLOB | VARCHAR, Text/UnicodeText/CLOB как text BLOB, типизированные string binds; NCHAR/NVARCHAR | String без длины получает 255; national types используют ISO8859_1; string binds через text BLOB требуют проверки планов |
| Boolean и даты | Boolean binds/projections, DATE/TIME/TIMESTAMP, исторические даты, проверенные TIMESTAMP timezone сценарии | Время имеет шаг 100 мкс; произвольные микросекунды не сохраняются |
| Enum | Ненативная строковая адаптация с validation | Нативного ENUM Firebird не добавляется |
| DDL таблиц и ограничений | Создание/удаление таблиц, PK, UNIQUE, FK, CHECK, комментарии в проверенных сценариях | DDL-транзакции приложение завершает самостоятельно; тестовый autocommit helper не является runtime-функцией |
| Identity и sequence | Identity с start/increment; NEXT VALUE FOR, sequence existence/list/reflection | Для PK рекомендуется явный `Identity()`; дополнительные identity options не реализованы |
| Computed columns | Virtual computed: `Computed(..., persisted=None/False)`, reflection `persisted=False` | Stored computed / persisted=True отклоняется |
| Views | Обычные views; SQLAlchemy `CreateView(or_replace=True)` переводится в CREATE OR ALTER VIEW | Не materialized/temporary views |
| Reflection | Столбцы, типы, PK/FK/UNIQUE/CHECK, индексы, identity/computed, views, comments, sequences | Только проверенные формы; get_multi_* может использовать последовательные fallback-запросы |
| GTT table options | Reflection `firebird_on_commit` для GLOBAL TEMPORARY TABLE | Не полное восстановление всех table options; GLOBAL TEMPORARY prefix при пересоздании задаётся явно |

## 3. Реализовано частично или с известными ограничениями

| Возможность | Что уже есть | Чего пока нет / что нельзя обещать |
|---|---|---|
| TIME WITH TIME ZONE | DDL/type adaptation; UTC SELECT roundtrip sync/async, NULL, 100 мкс, cached binds | Fixed-offset bind вызывает `KeyError('UTC+05:30')`. Encoder/decoder именованных зон используют today вместо опорной даты 2020-01-01 по source audit. Общий gate закрыт; persistence/reflection отдельно не проверены |
| Isolation levels | Get/set/values; READ COMMITTED, READ COMMITTED LEGACY, REPEATABLE READ, SNAPSHOT, SERIALIZABLE, AUTOCOMMIT | Нужны live проверки aliases, TPB semantics и pool reset. Серверный ReadConsistency влияет на различие READ COMMITTED вариантов |
| CTE | Основные серверные CTE-сценарии через компилятор | CTE placement внутри UPDATE/DELETE и другие закрытые DML-варианты не сертифицированы |
| Индексы выражений | COMPUTED BY, специальная компиляция и reflection | Несколько operands объединяются через `||`; это не универсальный многоколоночный expression index. Разбор сложных выражений ограничен |
| Descending/partial indexes | В компиляторе есть генерация DESCENDING/WHERE | Полный публичный контракт options и все формы отдельно не сертифицированы; смешанное направление колонок не поддерживается серверной моделью индекса |
| ORM | AsyncSession CRUD, явный Identity, savepoint/full rollback проверены | Полный ORM feature matrix и production-нагрузка не сертифицированы |
| Alembic | Opt-in интеграция; online create/drop table, add/drop/rename column через async run_sync, DDL rollback | Полные autogenerate/batch/alter/constraint/type/comment/identity migrations не сертифицированы; rename table и IF [NOT] EXISTS отклоняются |
| JSON/ARRAY | Компиляция в BLOB; ARRAY имеет сериализационный путь | Это не полноценные JSON expressions и не нативный SQL ARRAY API с bounds/slices/multidimensional wire support |

## 4. Не реализовано либо явно не поддерживается текущим API

| Возможность | Статус и причина |
|---|---|
| Server-side streaming через SQLAlchemy async | Отключено (`supports_server_side_cursors=False`); `AsyncConnection.stream()` не заявлен |
| Native multi-VALUES INSERT, настоящий bulk RETURNING | Не реализованы текущим диалектом; row-at-a-time fallback не заменяет native batching |
| Суммарный async executemany rowcount | Не предоставляется adapter: -1, а не счётчик всего пакета |
| SQLAlchemy regexp_match / regexp_replace | Явный CompileError. Нативный SIMILAR TO доступен как SQL, но имеет другую семантику и не подставляется вместо regexp search |
| Полноценные JSON/ARRAY/UUID/Interval API | Не реализованы/не заявлены; temporal RANGE с timedelta не является общим Interval-контрактом |
| Дополнительные identity min/max/cycle/cache | Компилятор не реализует эти options; не рассчитывать на них |
| UPDATE FROM, DELETE USING, two-phase API | Рабочий контракт текущего диалекта не заявлен; это не общий вывод об отсутствии аналогов в сервере |
| CREATE TABLE AS SELECT | Firebird 5 не поддерживает эту форму; автоматической эмуляции в диалекте нет. Альтернатива: CREATE TABLE, затем INSERT INTO SELECT |
| Отдельные SQL schemas | Firebird 5 не поддерживает; schema namespace не эмулируется |
| Stored computed columns, materialized/temporary views | Не поддерживаются в рассматриваемой серверной модели; диалект их не эмулирует |
| Tuple IN, SQL VALUES constructors, FETCH PERCENT/WITH TIES | Соответствующие API/формы не поддержаны текущим стеком |

Отсутствие возможности сервера не является дефектом диалекта. Наличие похожей серверной конструкции, в свою очередь, не доказывает готовность соответствующего SQLAlchemy API.

## 5. Исправления драйвера, необходимые для результата

Следующие работы выполнены в **pyfirebirdsql**, а не в компиляторе диалекта. Их необходимо учитывать при поставке:

- Корректное чтение signed INT128 и передача больших Decimal без молчаливого усечения до INT64.
- Материализация singleton RETURNING/procedure BLOB outputs в bytes/text вместо blob ID.
- Освобождение statements/cursors при полном commit/rollback, включая read-only транзакции; устранение удержания metadata locks в проверенных случаях.
- Исправление description/rowcount контракта для statements без результатов и освобождение async statements.
- Корректная обработка диагностик и проброс index key size errors вместо подавления неудачного DDL.
- Async rowcount API, lifecycle cleanup и отбрасывание транспорта после receive cancellation/timeout/EOF в проверенных сценариях.
- Исправление заголовка continuation bind metadata: использован protocol constant isc_info_sql_bind вместо неверного байта.

Часть async API была адаптирована после обновления upstream драйвера. Текущий AsyncSocketStream отправляет данные через задачи sock_sendall; старое утверждение о заведомо синхронных sends неприменимо к этой версии. Полная неблокируемость connect/send/lifecycle и поведение под нагрузкой всё ещё не доказаны.

Обычная установка зависимости из PyPI не гарантирует наличия перечисленных локальных исправлений. Полная неблокируемость или работоспособность native aio pool не следуют из успешных тестов SQLAlchemy pool.

## 6. Оставшиеся работы

1. Исправить fixed-offset TIME binds и anchor date именованных зон; проверить переход суток, NULL, запись/чтение и reflection перед открытием общего gate.
2. Проверить и исправить driver-native aio pool: в database-free аудите healthy release теряет соединение, есть обращения к отсутствующим API и вызовы async close без await.
3. Сертифицировать isolation aliases, реальные серверные режимы и сброс соединений в pool; проверить CTE/DML compiler placement.
4. При необходимости реализовать streaming, полноценные JSON/ARRAY API и расширенную интеграцию миграций как отдельные проекты, без обещания неподдерживаемых сервером SQL-форм.
5. Провести cross-version, concurrency/load, latency и сетевые fault-тесты. Успешный функциональный suite не заменяет эти проверки.

## 7. Источники и воспроизведение

- [Подробное руководство и риски](capabilities.ru.md) — содержит также исторические результаты; для текущего сводного статуса использовать этот отчёт.
- [Оставшиеся capability gates](capability-audit.ru.md).
- [Локальная установка и Alembic](local-release.ru.md).
- [Адаптация upstream CTAS tests](patches/README.md).
- Родительская wiki: `wiki/testing.md`, `wiki/handoff.md`, `wiki/next-steps.md`, `wiki/references.md`; последняя содержит ссылки на локальный Firebird 5 Language Reference.
- Последние логи: `baseline/phase-resume-final-firebirdsql.log`, `baseline/phase-resume-final-firebirdsql_async.log`, `baseline/phase-resume-regressions-final.log`. Эти артефакты локальные и не входят в поставку.

**Итог:** основной sync/async SQLAlchemy Core путь реализован и проходит оговорённый suite. Готовность не распространяется автоматически на все API SQLAlchemy, все timezone/array/bulk/streaming сценарии, полноценные миграции и production-устойчивость.
