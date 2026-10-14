# Контракт API v1

Исходная спецификация 1.0 от 14 октября 2026 года сохранена как проектный документ.
Пометки **NOT IMPLEMENTED** ниже описывают состояние этапа 2 на момент её фиксации;
они не являются текущим статусом backend. После MVP-реализации stages 3–13 точные
доступные пути/поля/статусы публикует работающий `/openapi.json`; сводка находится
в [README](../../README.md), ограничения — [LIMITATIONS](../LIMITATIONS.md).
`openapi-stage2.json` — исторический snapshot каркаса, а не актуальный API MVP.
Реальная LLM/ASR/диаризация по-прежнему отключены; demo fixture отмечается отдельно.

## 1. Маршруты каркаса этапа 2

### `GET /health/live`

Проверяет жизнь API-процесса, не требует подключения к БД.

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ok"}
```

### `GET /health/ready`

Проверяет БД и соответствие применённой миграции текущему head. Готовность
не означает, что бизнес-функции, worker-job queue или AI доступны.

```json
{"status":"ready","database":"ok","schema":"0001_bootstrap"}
```

Успех — `200`. Недоступная БД или несовпадающая миграция — `503`:

```json
{
  "error": {
    "code": "service_not_ready",
    "message": "Service is not ready.",
    "request_id": "request-id",
    "details": []
  }
}
```

Допускается безопасная причина в details без SQL, credentials, hostnames и URL БД.

### `GET /api/v1/capabilities`

Успех — `200`, не требует действующего модельного сервера:

```json
{
  "stage": 2,
  "processing": {"asr":"disabled","diarization":"disabled","llm":"disabled"},
  "business_api": "not_implemented"
}
```

`disabled` означает, что настоящее распознавание/анализ отсутствует. На этапе 2
нет демо-анализа через HTTP. Синтетические fixtures — файлы разработки.

## 2. Общие правила

Base path бизнес-API: `/api/v1`. JSON — UTF-8, `snake_case`; UUID — строки;
timestamp — RFC 3339 с offset; date — `YYYY-MM-DD`; timezone — IANA.
Поля и ошибки не принимают произвольный provider JSON без валидации.

### Ошибки и request_id

Формат ошибки унифицирован:

```json
{
  "error": {
    "code": "version_conflict",
    "message": "The resource has changed.",
    "request_id": "request-id",
    "details": [{"field":"expected_version","reason":"stale","current_version":4}]
  }
}
```

`details` — массив безопасных объектов; может быть пустым. Не включаем пароль,
token, SQL, путь хранения, transcript, исходный запрос и traceback. `request_id`
присваивается сервером или принимается только в допустимом формате/длине из
`X-Request-ID`, возвращается одноимённым response header и используется в логах.
Тексты message ориентированы на разработчика; frontend локализует code.

| HTTP | code | Значение/будущий пример |
|---|---|---|
| 400 | `invalid_request` | Некорректный запрос |
| 401 | `authentication_required` | Нет/истекла session |
| 403 | `csrf_failed`, `operation_forbidden` | Не прошла CSRF/нет разрешения действия |
| 404 | `not_found` | Нет ресурса или он чужой; existence не раскрывается |
| 409 | `version_conflict`, `invalid_transition`, `idempotency_conflict` | Версия/состояние/повтор с другим телом |
| 410 | `source_expired` | Собственный источник удалён по retention |
| 413 | `payload_too_large` | Превышен лимит запроса |
| 415 | `unsupported_media_type` | Формат не поддержан |
| 422 | `validation_error` | Неверные поля/срок/ссылки |
| 429 | `rate_limit_exceeded` | Limit login/upload; Retry-After |
| 500 | `internal_error` | Без traceback/секретов |
| 503 | `service_not_ready`, `provider_unavailable` | БД/миграция либо будущий provider |

Коды бизнес-ошибок проектные. На этапе 2 проверяются только ошибки имеющихся
служебных маршрутов, validation/404 и безопасная обработка внутренних ошибок.
Отказ CORS preflight возвращает `400 cors_request_denied` с message
`CORS request is not allowed.`. Validation details имеют вид
`{"location":["query","field"],"type":"int_parsing"}` без raw input и
Pydantic error message, которые могут раскрыть пользовательские значения.

### Пагинация и фильтры — NOT IMPLEMENTED

```json
{"items":[],"total":0,"limit":20,"offset":0}
```

`limit` 1..100, default20; `offset` ≥0, default0. `total` вычислен после фильтров и
проверки владельца. Default sort `created_at desc,id desc`; равные значения всегда
разрешает id. `sort` только из allowlist, например `due_asc/created_desc/priority_desc`.
Повтор tags передаётся как `tag_id=...&tag_id=...`; семантика v1 — все указанные tags.
Диапазоны timestamp полуоткрытые `[from,to)`. Пустой список — 200, не 404.

### Сессии и доступ — NOT IMPLEMENTED, этап 3

Предлагаются серверные opaque sessions: `HttpOnly`, `SameSite=Lax`, `Secure` при
HTTPS, ограниченный TTL, rotation при входе, revocation при logout. Token digest
хранится в БД, пароль — адаптивный hash. Web mutating requests проходят CSRF
проверку и Origin allowlist; пароль/login rate limit. Локальный HTTP режим с
insecure cookie разрешается явно только для development.

Все business routes проверяют owner и org в запросе к БД. Получать audio/evidence
или экспорт по guessed UUID без той же проверки нельзя. Наличие общего org
не открывает доступ всей команде. Служебные endpoints этапа 2 публичны и не
содержат пользовательских данных; это не пример будущей авторизации.

### Версия и идемпотентность — NOT IMPLEMENTED

Mutable resource содержит `version:1..N`. PATCH/переход принимает обязательное
`expected_version`; update выполняется условно. Устаревшее значение — 409, сервер
ничего не перезаписывает. Клиент перечитывает ресурс и предлагает объединение правок.

Uploads и demo-create требуют `Idempotency-Key`: непустая ASCII строка длиной
1..128 из allowlist символов. Scope: owner+method+route. Server сохраняет digest
тела (metadata+байты), status и результат не менее 24 часов. Тот же ключ/тело
повторяет исходный ответ и call_id; другой digest —409. Pending duplicate даёт
409 `idempotency_in_progress` с Retry-After. Новый ключ позволяет намеренно загрузить
тот же файл отдельным звонком. Очистка ключей не удаляет Call; клиенту документируется
окно гарантии. Action requests позже используют тот же механизм для безопасного replay.

## 3. Auth, clients и calls — NOT IMPLEMENTED

| Этап | Метод и путь | Вход | Успех |
|---|---|---|---|
| 3 | `POST /auth/login` | `{login,password}` | 200 `{user,csrf_token}`, session cookie |
| 3 | `POST /auth/logout` | CSRF | 204, cookie revoked |
| 3 | `GET /me` | Session | 200 `{id,organization_id,display_name}` |
| 4 | `GET /clients` | limit/offset, optional query | 200 page Client |
| 4 | `POST /clients` | `{display_name,contacts?,notes?}` | 201 Client, version1 |
| 4 | `GET /clients/{id}` | — | 200 Client |
| 4 | `PATCH /clients/{id}` | `{expected_version,...changes}` | 200 updated Client |
| 4 | `GET /clients/{id}/calls` | page | 200 разрешённые Call |
| 4 | `POST /calls` | multipart `audio`,`metadata`; key | 202 `{call_id,processing_url,version}` |
| 4 | `GET /calls` | page, client/source/demo/from/to | 200 page Call |
| 4 | `GET /calls/{id}` | — | 200 Call |
| 4 | `PATCH /calls/{id}` | `{expected_version,title?,client_id?,participants?}` | 200 Call |
| 4/13 | `DELETE /calls/{id}` | `{expected_version}` | 202 `{call_id,deletion_status:"pending"}` |
| 4/6 | `POST /demo/calls` | `{scenario_id}`; key | 202 call/provenance |

В metadata загрузки:

```json
{
  "title":"Обсуждение КП",
  "call_at":"2026-10-14T10:00:00+03:00",
  "timezone":"Europe/Minsk",
  "language":"ru",
  "source":"upload",
  "client_id":null,
  "participants":[],
  "processing_rights_confirmed":true,
  "notice_version":"v1"
}
```

`title` 1..200; client optional; `source` у upload — `upload/browser_recording`.
Отклоняются naive datetime, неизвестный timezone, неверный client owner и
неподтверждённое право загрузки. Date/offset/timezone должны согласовываться;
неоднозначный локальный момент при будущих DST-зонах требует offset.
`demo` не выбирается свободно в upload. Call.source и is_demo назначает server.
Просроченный job не восстанавливает удалённый call. Окончательное удаление может
занять время; повтор DELETE идемпотентен при том же ключе/условии.

Call response содержит metadata, `processing_status`, `analysis_status`,
`is_demo`, `provenance`, version и safe capability reasons. storage_key/секреты
в ответ не попадают. Исправление call_at/timezone, когда уже существуют derived
сроки, требует отдельного подтверждённого действия recalculation; обычный PATCH
не должен молча переносить уже принятые задачи.

## 4. Processing, audio, transcripts, result — NOT IMPLEMENTED

| Этап | Метод и путь | Вход | Успех/условия |
|---|---|---|---|
| 5 | `GET /calls/{id}/processing` | — | 200 stages, attempts, safe errors |
| 5 | `POST /calls/{id}/processing/retry` | `{stage,expected_version}` | 202; доступные failed/blocked стадии |
| 5 | `POST /calls/{id}/processing/cancel` | `{expected_version}` | 202; проверка отмены перед commit |
| 4/6 | `GET /calls/{id}/audio` | Range header optional | 200/206 stream; 410 expired |
| 6 | `GET /calls/{id}/transcript` | `revision_id?` | 200 TranscriptRevision, segments |
| 6 | `PATCH /calls/{id}/transcript` | base/current version, edited segments, mapping | 201 новая revision |
| 7 | `GET /calls/{id}/result` | — | 200 summary, candidates, provenance/capabilities |
| 7 | `POST /calls/{id}/analysis` | `{transcript_revision_id,expected_version,settings_version}` | 202 run; unavailable503 |
| 7 | `PATCH /calls/{id}/summary` | `{expected_version,summary?,client_message_draft?}` | 200 новая summary revision |

Segment API: `{id,position,speaker_id,participant_id,text,start_ms,end_ms}`.
start/end либо оба null, либо 0≤start≤end; fixture без реального аудио имеет null.
Transcript response включает `revision`, `source`, `is_demo`, `availability`.
PATCH не изменяет старые строки. mapping speaker→participant принадлежит тому
же call. result сообщает `requires_recheck`, если evidence использует старую revision.

Processing response проектируется как:

```json
{
  "call_id":"uuid",
  "version":1,
  "processing_status":"blocked",
  "analysis_status":"not_connected",
  "stages":[{"stage":"asr","status":"blocked","attempt":0,"reason":"provider_unavailable"}],
  "available_actions":[]
}
```

Аудио Range поддерживается только после owner check. `416` — диапазон за пределами
файла. Retention аудио не уничтожает отдельно разрешённый текст, но переход к аудио
честно показывает expired. Источники закрытого/удалённого call не возвращаются.

В будущей версии capabilities может добавиться доступность fixture/manual/model,
но текущий JSON этапа 2 фиксирован в разделе 1. Анализ для известного demo использует
allowlist fixture; для произвольного текста с disabled-провайдером возвращается
provider_unavailable. Внешний LLM endpoint/протокол этой спецификацией не выбран.

## 5. Agreements и tasks — NOT IMPLEMENTED

| Этап | Метод и путь | Вход | Успех |
|---|---|---|---|
| 8 | `GET /calls/{id}/agreements` | page, verification | 200 page Agreement |
| 8 | `POST /calls/{id}/agreements` | manual fields, optional evidence | 201 proposed manual Agreement |
| 8 | `GET /agreements/{id}` | — | 200 Agreement |
| 8 | `PATCH /agreements/{id}` | `{expected_version,...changes,confirm_changes?}` | 200 новая revision |
| 8 | `POST /agreements/{id}/accept` | `{expected_version,condition_resolution?}`; key | 200 accepted Agreement |
| 8 | `POST /agreements/{id}/reject` | `{expected_version,reason?}`; key | 200 rejected Agreement |
| 8 | `POST /agreements/{id}/unconfirm` | `{expected_version,reason}`; key | 200 proposed Agreement |
| 9 | `POST /agreements/{id}/execution` | `{expected_version,action:start/complete/cancel/reopen}`; key | 200 Agreement |
| 8 | `GET /agreements/{id}/evidence` | — | 200 evidence array и availability |
| 9 | `GET /tasks` | фильтры ниже | 200 page принятых Agreement |
| 9 | `GET /tasks/calendar` | `from,to` | 200 те же records + deadlines |

Agreement response:

```json
{
  "id":"uuid",
  "call_id":"uuid",
  "version":1,
  "action":"Отправить коммерческое предложение",
  "obligor_participant_id":"uuid",
  "recipient_participant_id":"uuid",
  "due":{
    "kind":"date_only","date":"2026-10-17","timezone":"Europe/Minsk",
    "original_text":"до 17 октября 2026",
    "basis_call_at":"2026-10-14T10:00:00+03:00",
    "normalization_source":"fixture","ambiguous":false,"ambiguity_reasons":[]
  },
  "condition":null,
  "needs_details":[],
  "verification":"proposed",
  "execution":"open",
  "overdue":false,
  "priority":"normal",
  "tag_ids":[],
  "confidence":{"value":null,"source":"unknown","calibration":null},
  "manual_confidence_override":null,
  "provenance":{"source":"fixture","is_demo":true},
  "requires_recheck":false,
  "evidence":[{
    "transcript_revision_id":"uuid","segment_id":"uuid",
    "start_cp":0,"end_cp":33,"quote":"Да, пришлю КП до 17 октября 2026.",
    "availability":"available","start_ms":null,"end_ms":null
  }]
}
```

В примере segment.text равен quote целиком и имеет длину 33 code points.
Истинный span всегда вычисляется по конкретному сохранённому segment, а не по
длине JSON. Поля confidence неизвестны до проверки
модели; `manual_confidence_override` не перезаписывает исходную оценку.

Validation: action 1..2000; priority `low/normal/high`; confidence 0..1 либо null;
due по дискриминатору в domain_model; references только этого call/owner;
evidence quote строго равен span. Пустые participants/due не выдумываются.
PATCH принятого Agreement требует `confirm_changes=true`; иначе 409
`confirmation_required`. Proposed/rejected редактирование возвращает proposed.
Условное предложение требует resolution до принятия; изменение known due на
unknown видно как needs_details, старые запланированные напоминания отменяются.

Tasks filters: `client_id`, `execution` (повторяемый), `priority`, `tag_id`, `overdue`,
`needs_details`, `due_from`, `due_to`, `accepted_from`, `accepted_to`, `is_demo`.
Default не включает cancelled, но accepted done доступны. Calendar не включает
unknown due, возвращает список пропусков отдельно. `open/in_progress/done/cancelled`
независимы от `proposed/accepted/rejected`. Неверный переход —409 invalid_transition.

## 6. Settings, notifications, exports — NOT IMPLEMENTED

| Этап | Метод и путь | Контракт |
|---|---|---|
| 9 | `GET/POST /tags` | page / `{name,color?}` →201 Tag |
| 9 | `PATCH/DELETE /tags/{id}` | expected_version; delete прекращает joins |
| 9 | `GET/POST /task-templates` | page / name+defaults →201 immutable revision |
| 9 | `PATCH /task-templates/{id}` | expected_version →200 новая revision |
| 9 | `GET/POST /trigger-rules` | page / phrase+enabled+kind →201 revision |
| 9 | `PATCH /trigger-rules/{id}` | expected_version →200 новая revision |
| 11 | `GET/PATCH /settings/reminders` | политика смещений/quiet hours, expected_version |
| 11 | `GET /notifications` | page, unread_only; только owner |
| 11 | `POST /notifications/{id}/read` | expected_version →200 read_at |
| 10 | `GET /exports/tasks.ics` | те же allowlist filters/explicit agreement_ids; authenticated file |
| 10 | `GET /exports/tasks.xlsx` | то же; authenticated file |
| 10 | `GET /agreements/{id}/deliveries` | page safe outbox state, без credentials |

Response выгрузки: правильный MIME и Content-Disposition; без публичного storage
URL. Отфильтрованная пустая выборка — валидный пустой файл. Невозможный календарный
элемент (unknown due/отсутствуют нужные поля) не создаётся с выдуманной датой; API
возвращает безопасное предупреждение header или предварительный manifest маршрутом,
уточняемым при реализации этапа 10. Export содержит только accepted records.

Webhook доставляется worker в локальный mock CRM; публичный endpoint для внешних
произвольных destinations в MVP не предоставляется. Payload: event_id, event_type,
agreement_id, version, accepted business fields. Idempotency и порядок версии
контролируются приёмником. Уведомления клиенту не отправляются автоматически.

## 7. Dashboard — NOT IMPLEMENTED

`GET /dashboard?accepted_from=...&accepted_to=...&mode=real` — 200. `mode=demo/real`
обязателен или default real. Когорта по accepted_at; время расчёта явно передаётся
в response как `as_of`, часовой пояс/метод известны клиенту.

```json
{
  "mode":"real",
  "as_of":"2026-10-14T12:00:00+03:00",
  "cohort":"accepted_at",
  "agreements_count":0,
  "completed_count":0,
  "overdue_count":0,
  "completion_rate":null,
  "saved_time":{"status":"not_measured","seconds":null,"method":null}
}
```

Completion rate использует accepted open/in_progress/done; cancelled исключён.
Общий agreements_count может включать cancelled, поэтому знаменатель rate
обязательно документируется отдельно. Demo savings имеет статус illustrative,
не результат ASR/LLM measurement. Никакой accuracy=90 в capability/dashboard нет.

## 8. Проверка контрактов перед реализацией

1. Создание Call не приравнивает очередь к выполненному ASR.
2. Изменение текста не ломает evidence: новая revision, исходная сохранена.
3. Версионный конфликт не допускает overwrite; owner проверяется прежде ответа.
4. Условие и неизвестный срок сохраняются без выдуманных значений.
5. Accepted Agreement появляется в tasks и производит delivery, rejected — нет.
6. Expired source возвращает availability, не копию удалённой цитаты.
7. .ics отличается от автоматической внешней синхронизации; webhook пока mock.
8. Контракт будущей модели остаётся внутренним адаптером, без выбранного runtime.
