import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mts_backend import worker


@pytest.mark.parametrize(("ready", "expected_code"), [(True, 0), (False, 1)])
async def test_worker_once_checks_readiness_and_disposes_engine(
    monkeypatch, settings, ready, expected_code
):
    monkeypatch.setattr(worker, "tick", AsyncMock())
    engine = MagicMock()
    engine.dispose = AsyncMock()
    checker = AsyncMock(return_value=ready)
    monkeypatch.setattr(worker, "build_engine", lambda configuration: engine)
    monkeypatch.setattr(worker, "check_readiness", checker)
    loop = asyncio.get_running_loop()
    add_signal = MagicMock()
    remove_signal = MagicMock()
    monkeypatch.setattr(loop, "add_signal_handler", add_signal)
    monkeypatch.setattr(loop, "remove_signal_handler", remove_signal)
    assert await worker.run_worker(settings, once=True) == expected_code
    checker.assert_awaited_once_with(engine, settings.db_connect_timeout_seconds)
    engine.dispose.assert_awaited_once()
    assert add_signal.call_count == remove_signal.call_count == 2
