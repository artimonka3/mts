"""Bounded local webhook delivery. No user supplied URL or HTTP redirects."""

import asyncio
import json
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from sqlalchemy import or_, select

from mts_backend.core.business import uid, utcnow
from mts_backend.db.models import Agreement, DeliveryAttempt, OutboxEvent

ALLOWED_URLS = {"http://mock-crm:8001/webhook", "http://127.0.0.1:8001/webhook"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_local(url, token, payload):
    if url not in ALLOWED_URLS or not token:
        return None, "configuration_disabled"
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Webhook-Token": token},
        method="POST",
    )
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=3) as response:
            code = response.status
            # Do not retain the remote response body.
            return code, "success" if 200 <= code < 300 else "http_error"
    except HTTPError as exc:
        return exc.code, "http_error"
    except (URLError, OSError, ValueError):
        return None, "network_error"


async def deliver_once(db, settings):
    url = getattr(settings, "crm_webhook_url", "http://mock-crm:8001/webhook")
    token = getattr(settings, "crm_webhook_token", "")
    if hasattr(token, "get_secret_value"):
        token = token.get_secret_value()
    if url not in ALLOWED_URLS or not token:
        return 0
    now = utcnow()
    event = await db.scalar(
        select(OutboxEvent)
        .where(
            or_(
                OutboxEvent.status.in_(["pending", "queued", "retry_wait"]),
                OutboxEvent.status == "delivering",
            ),
            OutboxEvent.not_before <= now,
        )
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if event is None:
        return 0
    agreement = await db.get(Agreement, event.agreement_id)
    if agreement is None or agreement.version != event.aggregate_version:
        event.status = "superseded"
        await db.commit()
        return 1
    maximum = getattr(settings, "crm_max_attempts", 3)
    if event.attempt >= maximum:
        event.status = "failed"
        await db.commit()
        return 1
    event.attempt += 1
    event.status = "delivering"
    event.not_before = now + timedelta(seconds=30)
    event_id, attempt, payload = event.id, event.attempt, dict(event.payload)
    # Claim persists before network I/O, so another worker cannot hold up SQL transactions.
    await db.commit()
    code, result = await asyncio.to_thread(send_local, url, token, payload)
    event = await db.get(OutboxEvent, event_id, with_for_update=True)
    if event.attempt != attempt or event.status != "delivering":
        return 1
    db.add(
        DeliveryAttempt(
            id=uid(),
            event_id=event_id,
            attempt=attempt,
            response_code=code,
            result=result,
            created_at=utcnow(),
        )
    )
    if result == "success":
        event.status = "delivered"
    elif attempt >= maximum or (code is not None and 400 <= code < 500 and code != 429):
        event.status = "failed"
    else:
        event.status = "retry_wait"
        event.not_before = utcnow() + timedelta(seconds=min(60, 2**attempt))
    await db.flush()
    return 1
