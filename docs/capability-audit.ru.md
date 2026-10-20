# Остаточные capability gates

Это классификация по Firebird 5 Language Reference, исходникам и точечным проверкам, а не заявление о полной поддержке SQLAlchemy. Локальный reference: родительский wiki/references.md и firebird-50-language-reference.text.txt.

## Проверены и открыты

| Gate | Основание и проверка |
|---|---|
| boolean_col_expressions | §3.6.1 допускает predicate в SELECT. Собственные sync/async тесты проверяют сравнения, AND/NOT, Python bool/None. Дополнительно исправлены нетипизированные Boolean projection binds: теперь CAST(... AS BOOLEAN) |
| date_historic, datetime_historic | §3.4.1: годы 0001–9999. Штатные тесты проверяют bind, executemany, literal INSERT/WHERE и roundtrip годов 1, 99, 100, 999, 1000, 1752, 1753, 1899, 1969. Старый комментарий касался другого драйвера |
| percent_schema_names | §2.3.2: quoted identifiers. Название gate не означает SQL schemas: suite проверяет `%` и пробелы в таблицах/колонках. Single/executemany и row-at-a-time RETURNING проходят |

Official группа Historic/PercentSchemaNames/Boolean: sync/async каждый 26 passed. После открытия class gates полный suite вырос с 1516 до 1537 collected cases: **1042 passed, 495 skipped** для каждого sync/async, 0 failures/errors. Число skips не уменьшилось: эти классы ранее исключались ещё до collection. CTAS guard остаётся отдельной локальной адаптацией upstream suite.

## Остаток: не открывать без runtime-проверки

| Gates / область | Вывод |
|---|---|
| time_timezone | Серверный TIME WITH TIME ZONE существует (§3.4.2–3.4.5), wire paths есть. Нужны UTC/nonzero offset, переход суток, NULL; named zones не считать автоматически поддержанными |
| isolation_level | Get/set/values реализованы, но aliases/TPB semantics, checkout/reset и execution options требуют отдельной проверки (§13.1.1) |
| ctes_with_update_delete | §6.1.17 допускает WITH-query в подзапросе DML, не гарантирует верхнеуровневое WITH UPDATE. Нужен аудит compiler placement, не простое открытие gate |
| array_type | Серверные arrays существуют (§3.8), но generic mapping к BLOB не реализует bounds/slices/multidimensional wire API. Отдельная существенная работа |
| microseconds gates | §3.4: шаг 100 μs. Наличие fractional seconds не означает exact roundtrip произвольных Python microseconds |
| per-column index ASC/DESC | §5.5.1: направление всего индекса, не отдельных колонок. Mixed direction gate не открывать |
| SQL schemas, CTAS, materialized/temp views | Несовместимые нативные формы. Не подменять schema namespace и не называть CREATE+INSERT нативным CTAS |
| tuple IN, VALUES constructors, native multi-VALUES | Нативные SQL gaps; row-at-a-time RETURNING fallback не является native batching |
| regexp, stored computed, FETCH PERCENT/WITH TIES | Закрытие обосновано: SQL SIMILAR TO не regexp-search (§4.2.2), computed virtual (§5.4.1), соответствующих FETCH форм нет (§6.1.10) |

495 skips не равны 495 отсутствующим возможностям. Reflection даёт 361 параметризованный случай, RETURNING 26, TableViaSelect 23; decorators пересекаются. Кроме того, закрытые class gates могут скрывать случаи до collection. Полной взаимно-однозначной раскладки skips по gates пока нет.
