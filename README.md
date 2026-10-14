# МТС: Backend MVP, трек №2

Backend для загрузки разговора → результата → подтверждённых задач → экспорта,
напоминаний и дашборда. Python 3.12 / FastAPI / PostgreSQL / SQLAlchemy / Alembic.
API, worker и локальный mock CRM — отдельные процессы.

**LLM, ASR и диаризация отключены.** Известные demo-сценарии используют синтетические
text-only fixtures. Произвольное аудио принимается/проверяется/подготавливается;
текст и договорённости можно вводить вручную. Реальной модельной точности нет.

## Быстрый запуск

Нужны Docker с Compose v2, Python 3.12 для локальных команд и свободные порты
8000/55432. Из корня проекта:

```sh
make init
make up-host
make seed-host
```

`make init` создаёт отсутствующие ключи и пароль в `.env`, не заменяя существующие.
Логины: `demo` и `demo2`; пароль берётся из `MTS_DEMO_PASSWORD` в локальном `.env`.
Seed никогда не сбрасывает существующий пароль. `.env` не коммитится.

[Swagger](http://127.0.0.1:8000/docs) · [OpenAPI](http://127.0.0.1:8000/openapi.json)
· [Готовность](http://127.0.0.1:8000/health/ready).

`up-host` хранит PostgreSQL в `.local/postgres`, аудио — в `.local/audio`.
На этом компьютере виртуальный Docker-диск был заполнен, поэтому используется этот
режим. При достаточном Docker-диске доступны `make up` / `make seed` с named volume.
Два режима хранят разные базы; выбирайте один последовательно.

```sh
docker compose -f compose.yaml -f compose.host-storage.yaml ps -a
make logs-host
make down-host
```

Остановка сохраняет данные. Ключи шифрования нужно хранить вместе с резервной
копией отдельно от БД; потерянный ключ не восстанавливается из данных. Не удаляйте
`.local/postgres`/`PG_VERSION` при ошибке запуска. Если Docker частично инициализировал
кластер и роль существует, но configured DB отсутствует, сначала проверьте список
баз, затем создайте только отсутствующую пустую базу и повторите `make up-host`.
Не используйте reset/prune как универсальное исправление.

## Что работает

- Cookie-вход, CSRF, logout, persistent login throttling, owner-only доступ.
- Клиенты, upload/browser recording file, demo, metadata, аудио Range и подготовка
  FFmpeg в worker. Нет записи телефонного звонка на устройстве.
- Версии расшифровки/summary, evidence по Unicode spans и immutable история.
- Договорённости: правки, accept/reject/unconfirm, execution; optimistic version
  и идемпотентность действий. Принятая договорённость является задачей.
- Задачи, фильтры, календарь, теги/шаблоны/триггеры и буквальный preview.
- ICS/XLSX и atomic outbox в локальный mock CRM с retry/dedup/version/tombstones.
- Напоминания, очередь подтверждений, read/unread; дашборд отдельно demo/real.
- Шифрование private text/JSON/audio, retention и удаление источников/копий.

Машиночитаемый текущий контракт выдаёт `/openapi.json`. Документы `docs/spec` —
исходная спецификация; если примеры отличаются, сверяйтесь с текущими схемами.
Общие мутации принимают `Origin` и `X-CSRF-Token` (из login или `/me`), cookie session.
Создание demo/upload и переходы Agreement дополнительно требуют `Idempotency-Key`.
Правки и переходы принимают актуальный `expected_version`; stale →409.

## Проверки и демо

```sh
make setup
make check
python3 tools/evaluate.py
```

Без `MTS_TEST_DATABASE_URL` PostgreSQL integration tests пропускаются. Используйте
отдельную тестовую БД, не рабочую: `MTS_TEST_DATABASE_URL=postgresql+psycopg://…/mts_test`.
Для encrypted fixtures передайте `MTS_DATA_ENCRYPTION_KEY` в окружение процесса
тестирования. Ошибка ключа должна прекращать доступ, а не выдавать plaintext.
Проверки создания/отката миграций используют отдельную **пустую** БД через
`MTS_BOOTSTRAP_TEST_DATABASE_URL`; её нельзя совмещать с API test DB.
Локальный аудио-тест требует FFmpeg/ffprobe; живой Docker smoke выполняется
командой `python3 scripts/smoke_mvp.py` после seed. Он создаёт и удаляет свои звонки.

`tools/evaluate.py` без predictions честно возвращает `not_measured`. Для сравнения
внешних результатов: `python3 tools/evaluate.py --predictions predictions.json`.
Формат — объект с ключами dialogue_id и `{predicted_keywords:[…], agreements:[…]}`;
agreement содержит action/participant refs/due, optional gold_id для совмещения.
Ключевые фразы, полные договорённости и поля имеют отдельные метрики. Это сравнение
predictions на development corpus, а не доказательство точности ASR/LLM ≥90%.

[Итоги и ревью](docs/MVP_STATUS.md) · [Демо на 3 минуты](docs/DEMO.md) · [Ограничения](docs/LIMITATIONS.md)
· [Исходный план](План_Backend_МТС_трек_2.md) · [Ревью этапов](docs/reviews).
