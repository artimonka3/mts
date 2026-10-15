# Backend MVP: итог первого прохода

14 октября 2026. Реализован backend по этапам 1–13 в FAMCS/hackaton_mts.
Настоящие ASR/diarization/LLM отключены: полный автоматический путь доступен только
для известных synthetic text-only demo. Произвольный файл можно загрузить,
подготовить и дополнить ручной расшифровкой и договорённостями.

## Этапы и короткое ревью

| Этап | Результат | Быстрое ревью |
|---|---|---|
| 1 | Мини-ТЗ, ERD, контракты, 24 synthetic диалога | [01](reviews/stage_01.md) |
| 2 | FastAPI, PostgreSQL, Alembic, Compose | [02](reviews/stage_02.md) |
| 3 | Бизнес-БД, вход, cookie/CSRF, изоляция владельцев | [03](reviews/stage_03.md) |
| 4 | Клиенты, звонки, upload/demo, encrypted audio и Range | [04](reviews/stage_04.md) |
| 5 | Jobs, lease/heartbeat/retry/cancel, FFmpeg | [05](reviews/stage_05.md) |
| 6 | Неизменяемые версии текста и говорящие | [06](reviews/stage_06.md) |
| 7 | Демо-анализ и редактирование summary | [07](reviews/stage_07.md) |
| 8 | Источники, правки и подтверждение договорённостей | [08](reviews/stage_08.md) |
| 9 | Задачи, статусы, фильтры, теги и настройки | [09](reviews/stage_09.md) |
| 10 | ICS/XLSX и надёжная доставка в mock CRM | [10](reviews/stage_10.md) |
| 11 | Напоминания и внутренние уведомления | [11](reviews/stage_11.md) |
| 12 | Метрики с разделением demo/real | [12](reviews/stage_12.md) |
| 13 | Сквозная проверка, encryption/retention/delete/backup | [13](reviews/stage_13.md) |

В каждом ревью: что сделано, небольшие проверки, проблемы → решения, приёмка
и честная оценка ограничений. Дополнительные retention-проверки:
[stage_13_tests](reviews/stage_13_tests.md).

## Фактически проверено

- `make check` из целевой папки: **96 passed, 1 skipped**, 15,80 с;
  Ruff check и format — PASS. PostgreSQL integration и миграции с нуля проверены
  в двух разных выделенных test DB. Пропуск — FFmpeg отсутствует на хосте.
- Отдельно `scripts/smoke_mvp.py` на живом Docker: demo → accept → ICS/XLSX →
  delivered mock CRM → complete → dashboard; загруженный WAV с неверным
  расширением/MIME проверен по содержимому, зашифрован и подготовлен FFmpeg;
  ASR честно blocked, near-zero signal даёт silent_audio. Smoke удалил свои звонки.
- Docker API/db healthy; migrate exit 0; worker и mock CRM работают. Реальная
  схема `0003_encrypted_metadata`, live/ready/capabilities HTTP 200.
- Сохранённый [OpenAPI MVP](api/openapi-mvp.json) совпадает с живым API: 46 paths.
- Backup тестовой БД восстановлен в отдельную пустую БД; перезапись непустой
  отклонена. [Инструкция](operations/backup_restore.md).
- Точность моделей и экономия времени **не измерены**. Инструмент evaluate без
  predictions возвращает not_measured; ≥90% не заявляется.

## Нормально / требует следующего ревью

Нормально для демонстрации: независимые состояния предложения/задачи, owner-only
доступ, конфликт версий, идемпотентные повторы, сохранность правок, настоящая
подготовка аудио и показ ограничений моделей, отзыв/удаление в mock CRM.

Перед реальным развёртыванием: общее ревью безопасности/нагрузки, HTTPS и защищённые
cookies, управление ключами/ротация, политика внешних backup и актуальная юридическая
проверка. Фильтры небольших разрешённых выборок выполняются в Python; VAD,
потоковый ASR, реальная LLM, frontend и командные роли остаются отдельной очередью.

Docker изначально не имел места для FFmpeg. Удалён неиспользуемый build cache
(7,138 ГБ), затем сборка прошла; базы/volumes, контейнеры и образы не удалялись.
Используется host-storage. Named-volume запуск новой полной версии отдельно
не проверялся. Изменения не закоммичены и не отправлены в remote.

## Как посмотреть

Стенд: http://127.0.0.1:8000/docs. Логины demo/demo2, пароль — MTS_DEMO_PASSWORD
в локальном .env (общий для явно созданных demo аккаунтов). Swagger показывает
X-CSRF-Token; cookie выставляется login. [Демо на 3 минуты](DEMO.md).
Повторный запуск из корня проекта: make up-host; seed — make seed-host.
Ключи и существующие пароли при обычном запуске не заменяются.
