"""MVP worker: leased audio jobs, reminders, retention and local CRM delivery."""

import argparse
import asyncio
import logging
import signal

from mts_backend.core.config import Settings, get_settings
from mts_backend.core.logging import configure_logging, log_event
from mts_backend.db.readiness import build_engine, check_readiness


async def run_worker(settings: Settings, *, once: bool = False) -> int:
    configure_logging(settings.log_level)
    engine = build_engine(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGTERM, signal.SIGINT)
    for handled_signal in signals:
        loop.add_signal_handler(handled_signal, stop.set)
    log_event("worker_started", mode="mvp_worker")
    try:
        while not stop.is_set():
            ready = await check_readiness(engine, settings.db_connect_timeout_seconds)
            log_event(
                "worker_heartbeat",
                level=logging.INFO if ready else logging.WARNING,
                ready=ready,
                mode="mvp_worker",
            )
            if ready:
                try:
                    await tick(engine, settings)
                except Exception:
                    log_event("worker_tick_failed", level=logging.ERROR)
                    if once:
                        return 1
            if once:
                return 0 if ready else 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
        return 0
    finally:
        for handled_signal in signals:
            loop.remove_signal_handler(handled_signal)
        await engine.dispose()
        log_event("worker_stopped", mode="mvp_worker")


async def tick(engine, settings):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from mts_backend.integrations.delivery import deliver_once
    from mts_backend.processing.jobs import process_one
    from mts_backend.processing.retention import sweep
    from mts_backend.reminders.service import notify_due

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions.begin() as db:
        await sweep(db, settings)
    await process_one(engine, settings)
    async with sessions.begin() as db:
        await notify_due(db, settings)
    async with sessions() as db:
        await deliver_once(db, settings)
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check readiness and process one worker tick, then exit.",
    )
    arguments = parser.parse_args()
    try:
        settings = get_settings()
        code = asyncio.run(run_worker(settings, once=arguments.once))
    except KeyboardInterrupt:
        code = 0
    except Exception:
        configure_logging("ERROR")
        log_event("worker_initialization_failed", level=logging.ERROR, mode="mvp_worker")
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
