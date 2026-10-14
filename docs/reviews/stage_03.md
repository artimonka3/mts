# Этап 3 — БД, вход и принадлежность

**Вердикт: нормально для MVP.** Миграция `0002_business` создаёт 23 таблицы: версии,
очередь, напоминания и outbox подготовлены сразу, чтобы следующие этапы не ждали БД.
Composite FK связывают владельца с организацией, звонок с его клиентом и дочерние
ресурсы со звонком. JSON snapshots сознательно упрощают физическую модель из ERD.

Сделано: opaque cookie session (TTL, rotation, logout, digest в БД), salted scrypt,
CSRF header + проверка Origin, устойчивое между процессами ограничение входа по
аккаунту и IP. Общая транзакция запроса commit/rollback. Seed явный:
`MTS_DEMO_PASSWORD=... python -m mts_backend.auth.seed`; создаёт `demo`, `demo2`,
существующие пароли сохраняет. Клиенты: CRUD, поиск, pagination, история звонков,
версия/409 и audit. Данные второго пользователя недоступны даже в общей организации.

Малые тесты: **2 unit + 2 PostgreSQL integration пройдены**. Проверены hash/salt,
неверный пароль, восстановление CSRF через `/me`, запрет unsafe mutation без token
и с чужим Origin, CRUD клиента, stale version, owner isolation, logout, сохранение
login throttling и 429. Миграция применена к отдельной `mts_mvp_test`.

Проблема: sandbox запретил TCP localhost при первой проверке — повторен разрешённый
запуск только на выделенной тестовой БД. Проблема: выброшенный 401 откатывал бы запись
неуспешного входа — login возвращает безопасный error response, позволяя commit attempts.

Приёмка: [x] migration работает; [x] cookie и password не хранятся открытым текстом;
[x] logout/TTL; [x] CSRF; [x] persistent throttling; [x] owner-only CRUD; [x] version 409.
Позже: регистрация/SSO/recovery, менеджер команды, ротация/очистка старых sessions.
Это MVP security, не результат внешнего pentest.
