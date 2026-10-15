# Демонстрация backend за 3–4 минуты

Предварительно: `make init`, `make up-host`, `make seed-host`; readiness200.
Используйте синтетический syn_01. Это text-only fixture с provenance, а не
успешное распознавание или вызов LLM. Фронтенд React реализуется отдельно.

| Время | Что показываем | Ожидаемое поведение |
|---|---|---|
| 0:00–0:40 | Вход и demo в один запрос | Cookie session, готовый fixture result |
| 0:40–1:20 | Текст, summary, evidence, предложенная договорённость | Source spans; proposed ещё не задача |
| 1:20–2:00 | Accept, правка срока, повтор запроса | Та же Agreement в tasks; version; безопасный replay |
| 2:00–2:40 | ICS/XLSX, deliveries, notification | Date-only без выдуманного часа; локальная CRM |
| 2:40–3:20 | Complete и dashboard demo/real | Выполнение выключает напоминания; demo не смешивается с real |
| 3:20–3:40 | Capabilities и ограничения | LLM/ASR disabled; accuracy not_measured |

HTTP последовательность ниже запускается из корня через `backend/.venv/bin/python`
после `make setup`. Пароль не выводится, cookie остаётся в памяти. Выгрузки сохраняются
только в `.local`. Заголовки Origin/CSRF показаны явно для будущего React-клиента.

```python
import json, os, time, urllib.request, http.cookiejar
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from uuid import uuid4

base = "http://127.0.0.1:8000"
env = dict(line.split("=", 1) for line in Path(".env").read_text().splitlines()
           if "=" in line and not line.startswith("#"))
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
csrf = None

def request(path, method="GET", body=None, key=None, binary=False):
    headers = {"Origin": base, "Content-Type": "application/json"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    if key:
        headers["Idempotency-Key"] = key
    payload = json.dumps(body).encode() if body is not None else None
    with opener.open(urllib.request.Request(base + "/api/v1" + path,
                     data=payload, headers=headers, method=method), timeout=10) as response:
        raw = response.read()
        return raw if binary else (json.loads(raw) if raw else None)

login = request("/auth/login", "POST", {"login": "demo", "password": env["MTS_DEMO_PASSWORD"]})
csrf = login["csrf_token"]
created = request("/demo/calls", "POST", {"scenario_id": "syn_01"}, str(uuid4()))
call_id = created["call_id"]
result = request(f"/calls/{call_id}/result")
agreement = result["agreements"][0]
print("Fixture:", call_id, agreement["action"], agreement["verification"])
key = str(uuid4())
acceptance = {"expected_version": agreement["version"]}
agreement = request(f"/agreements/{agreement['id']}/accept", "POST", acceptance, key)
replay = request(f"/agreements/{agreement['id']}/accept", "POST", acceptance, key)
assert replay["version"] == agreement["version"]

# For a reproducible reminder demonstration, explicitly choose a near instant.
due_at = (datetime.now(ZoneInfo("Europe/Minsk")) + timedelta(seconds=5)).isoformat()
agreement = request(f"/agreements/{agreement['id']}", "PATCH", {
    "expected_version": agreement["version"], "confirm_changes": True,
    "due": {"kind": "instant", "at": due_at, "timezone": "Europe/Minsk"},
})
selected = "?agreement_ids=" + agreement["id"]
for extension in ("ics", "xlsx"):
    Path(f".local/demo_tasks.{extension}").write_bytes(
        request(f"/exports/tasks.{extension}" + selected, binary=True))
time.sleep(8)
print("Delivery:", request(f"/agreements/{agreement['id']}/deliveries")["items"])
print("Notifications:", request("/notifications")["total"])
agreement = request(f"/agreements/{agreement['id']}/execution", "POST", {
    "expected_version": agreement["version"], "action": "complete"}, str(uuid4()))
print("Execution:", agreement["execution"])
print("Demo dashboard:", request("/dashboard?mode=demo"))
print("Real dashboard:", request("/dashboard?mode=real"))
```

Для показа date-only экспорта скачайте ICS до правки срока: `DTSTART;VALUE=DATE`,
без добавленного времени. Неизвестный срок виден в tasks с `needs_details=true`,
но пропускается в календаре/напоминаниях. Прочтение notification:
`POST /notifications/{id}/read` с текущим expected_version.

Отдельная отрицательная демонстрация: загрузить настоящий короткий файл и дождаться
prepare; обработка остановится с disabled ASR. Ручная расшифровка/договорённость
доступны, автоматический анализ произвольного текста возвращает503. Аккаунт demo2
не может открыть чужой call/agreement/audio/export по UUID.
