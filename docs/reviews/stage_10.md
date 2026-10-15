# Этап 10 — экспорт и локальная CRM

**Сделано:** приватные ICS/XLSX используют ту же разрешённую выборку, включая
explicit agreement_ids. ICS: стабильный UID, SEQUENCE, date-only, UTC instant,
экранирование и folding по 75 UTF-8 octets; неизвестные сроки пропускаются с
X-Skipped-Count. XLSX: действие/клиент/участники/срок/статус/приоритет/теги/звонок/
источник; текстовые ячейки исключают formula injection.

Atomic outbox создаётся вместе с изменением Agreement. Worker отпускает SQL
транзакцию до HTTP, использует timeout и максимум три попытки. Разрешены только
преднастроенные локальные адреса mock CRM, без redirects и proxy environment.
Отдельный приёмник требует secret, хранит event/version/tombstones в PostgreSQL;
повтор/старая версия не создают копию. Полное deleted окончательно закрывает record.

**Маленькая проверка:** четыре formula cases, UTF-8 folding/escaping/date-only/
unknown; PostgreSQL — atomic revoke, dedup, stale update, terminal tombstone,
delivery attempt и bounded retry. Общий набор stages 9–11 — 16 тестов.

**Проблема → решение:** снятие подтверждения должно очищать внешнюю запись,
поэтому отправляется revoked без текста. Deleted имеет отдельный terminal flag,
чтобы позднее обновление не воскресило запись. При смене версии старое событие
помечается superseded.

**Приёмка:** XLSX читается openpyxl; ICS проходит структурные проверки; повтор
webhook не дублирует данные; недоступность приёмника оставляет retry/failed event.

**Оценка:** нормально для demo. Фактический импорт файла в конкретный desktop
календарь/Excel пока не проверен. Файловый ICS не отзывает скачанные пользователем
копии. CRM — локальная имитация; реальные CRM не подключены.
