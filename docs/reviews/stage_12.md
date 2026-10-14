# Этап 12 — дашборд

**Статус: готово для MVP.** Owner-only статистика с отдельными real/demo режимами,
когорта по accepted_at, counts accepted/proposed/completed/cancelled/overdue.
Completion rate исключает cancelled из знаменателя; пустая когорта возвращает null.

**Малые проверки:** PostgreSQL dashboard/retention набор прошёл (3 теста всего).
Проверены 3 accepted задачи open/done/cancelled: denominator=2, completion_rate=0.5,
overdue=1; чужая задача исключена; real не включает demo; будущий accepted_from
даёт пустую когорту. Saved time и model accuracy честно `not_measured`.

**Проблемы → решение:** демонстрационные записи выделены явно, чтобы не улучшать
показатели реальных звонков. Экономия времени остаётся null до независимого замера.
**Приёмка:** совпадающие фильтры дают стабильную когорту, пустая выборка не вызывает
деление на ноль. Командный обзор руководителя оставлен корпоративному roadmap.
