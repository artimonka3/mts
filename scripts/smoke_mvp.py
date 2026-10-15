"""Live local MVP smoke. Creates and deletes only its own calls; no real ASR/LLM."""

import io
import json
import math
import struct
import time
import uuid
import wave
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

root = Path(__file__).resolve().parents[1]
values = dict(
    line.split("=", 1)
    for line in (root / ".env").read_text().splitlines()
    if "=" in line and not line.startswith("#")
)
base = "http://127.0.0.1:8000"
client = build_opener(HTTPCookieProcessor(CookieJar()))
headers = {}


def request(
    method, path, body=None, key=False, raw=None, content_type=None, expected=200
):
    request_headers = {**headers}
    if key:
        request_headers["Idempotency-Key"] = uuid.uuid4().hex
    data = raw
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        content_type = "application/json"
    if content_type:
        request_headers["Content-Type"] = content_type
    try:
        with client.open(
            Request(base + path, data=data, method=method, headers=request_headers),
            timeout=8,
        ) as response:
            status = response.status
            content = response.read()
    except HTTPError as error:
        status = error.code
        content = error.read()
    assert status == expected, f"{method} {path}: {status}, expected {expected}"
    return json.loads(content) if content and content[:1] in (b"{", b"[") else content


def await_state(call_id, wanted):
    end = time.monotonic() + 25
    while time.monotonic() < end:
        state = request("GET", f"/api/v1/calls/{call_id}/processing")
        if state["processing_status"] in wanted:
            return state
        time.sleep(0.5)
    raise AssertionError("Worker processing timeout")


def upload(silent=False):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        samples = [
            0 if silent else int(1200 * math.sin(2 * math.pi * 440 * i / 16000))
            for i in range(8000)
        ]
        wav.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    audio = stream.getvalue()
    metadata = {
        "title": "Smoke signal",
        "call_at": "2026-10-14T10:00:00+03:00",
        "timezone": "Europe/Minsk",
        "source": "browser_recording",
        "processing_rights_confirmed": True,
        "notice_version": "smoke-v1",
    }
    boundary = uuid.uuid4().hex
    raw = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
        + json.dumps(metadata).encode()
        + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="untrusted.exe"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        + audio
        + f"\r\n--{boundary}--\r\n".encode()
    )
    result = request(
        "POST",
        "/api/v1/calls",
        key=True,
        raw=raw,
        content_type=f"multipart/form-data; boundary={boundary}",
        expected=202,
    )
    return result["call_id"], audio


calls = []
try:
    login = request(
        "POST",
        "/api/v1/auth/login",
        {"login": "demo", "password": values["MTS_DEMO_PASSWORD"]},
    )
    headers = {"Origin": base, "X-CSRF-Token": login["csrf_token"]}
    demo = request(
        "POST", "/api/v1/demo/calls", {"scenario_id": "syn_01"}, key=True, expected=202
    )
    calls.append(demo["call_id"])
    result = request("GET", f"/api/v1/calls/{calls[-1]}/result")
    agreement = (result.get("agreements") or result.get("candidates"))[0]
    accepted = request(
        "POST",
        f"/api/v1/agreements/{agreement['id']}/accept",
        {"expected_version": agreement["version"]},
        key=True,
    )
    assert request("GET", "/api/v1/exports/tasks.ics")[:15] == b"BEGIN:VCALENDAR"
    assert request("GET", "/api/v1/exports/tasks.xlsx")[:2] == b"PK"
    deadline = time.monotonic() + 20
    delivered = False
    while time.monotonic() < deadline:
        deliveries = request("GET", f"/api/v1/agreements/{agreement['id']}/deliveries")
        if any(x.get("status") == "delivered" for x in deliveries["items"]):
            delivered = True
            break
        time.sleep(0.5)
    assert delivered, "Mock CRM did not receive accepted task"
    completed = request(
        "POST",
        f"/api/v1/agreements/{agreement['id']}/execution",
        {"expected_version": accepted["version"], "action": "complete"},
        key=True,
    )
    assert completed["execution"] == "done"
    assert request("GET", "/api/v1/dashboard?mode=demo")["completed_count"] >= 1
    print("PASS demo: result → accept → ICS/XLSX → mock CRM → complete → dashboard")
    identifier, audio = upload()
    calls.append(identifier)
    assert request("GET", f"/api/v1/calls/{identifier}/audio") == audio
    state = await_state(identifier, {"blocked", "failed"})
    assert state["processing_status"] == "blocked", str(state)
    assert state["analysis_status"] == "not_connected"
    assert state["stages"][0]["status"] == "succeeded"
    print(
        "PASS audio: MIME/extension spoof ignored; encrypted upload → real FFmpeg → ASR blocked"
    )
    identifier, _ = upload(silent=True)
    calls.append(identifier)
    state = await_state(identifier, {"failed"})
    assert state["stages"][0]["reason"] == "silent_audio"
    print("PASS silence: explicit silent_audio failure")
finally:
    for identifier in calls:
        call = request("GET", f"/api/v1/calls/{identifier}")
        request(
            "DELETE",
            f"/api/v1/calls/{identifier}",
            {"expected_version": call["version"]},
            expected=202,
        )
    if headers:
        request("POST", "/api/v1/auth/logout", expected=204)
print("PASS cleanup: smoke calls deleted, session revoked")
