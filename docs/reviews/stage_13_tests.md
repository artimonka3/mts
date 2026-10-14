# Этап 13 — быстрые проверки retention и удаления

Три PostgreSQL-теста dashboard/retention прошли. Expired transcript и summary
очищаются; quote/context и due.original_text исчезают из agreement, всех revisions
и IdempotencyRecord response. Принятая задача сохраняется и остаётся редактируемой.

Полное удаление отменяет running job даже без AudioAsset, очищает lease, снимки,
notifications и активные reminders. Старые outbox payload очищены; актуальный
`deleted` tombstone сохранён. Local mock CRM сразу хранит терминальный tombstone:
старый event даже с большей version не восстанавливает удалённые данные.

Исправлены: зависимость отмены от наличия аудио, копии quote в replay, ошибка
редактирования задачи после удаления evidence-quote. Проверки создают отдельные
случайные сущности и целиком откатывают транзакции. Проверки настоящей CRM/правовых
сроков не проводились: интеграция пока локальная имитация.
