import asyncio
import time
from contextlib import asynccontextmanager

import pytest

from app.api.routes import live
from app.main import app
from app.stt.base import SpeechToTextProvider, SpeechToTextSession, TranscriptEvent
from app.stt.factory import get_stt_provider


class ScriptedSession(SpeechToTextSession):
    """After audio ends, emits (delay, event) pairs, then stays open like a real provider."""

    def __init__(self, script: list[tuple[float, TranscriptEvent]]) -> None:
        self.script = script
        self.ended = asyncio.Event()

    async def send_audio(self, pcm: bytes) -> None:
        pass

    async def end_audio(self) -> None:
        self.ended.set()

    async def events(self):
        await self.ended.wait()
        for delay, event in self.script:
            await asyncio.sleep(delay)
            yield event
        await asyncio.Event().wait()


class ScriptedProvider(SpeechToTextProvider):
    def __init__(self, script: list[tuple[float, TranscriptEvent]]) -> None:
        self.script = script

    @asynccontextmanager
    async def open_session(self):
        yield ScriptedSession(self.script)


@pytest.fixture(autouse=True)
def short_timings(monkeypatch):
    monkeypatch.setattr(live, "SETTLE_SEC", 0.2)
    monkeypatch.setattr(live, "PENDING_IDLE_SEC", 0.5)
    monkeypatch.setattr(live, "FLUSH_TIMEOUT_SEC", 2.0)


def run_session(client, script) -> tuple[list[dict], float]:
    """Returns the messages received after stop and the seconds until done."""
    app.dependency_overrides[get_stt_provider] = lambda: ScriptedProvider(script)
    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_bytes(b"\x00\x00" * 1600)
        ws.send_json({"type": "stop"})
        stopped_at = time.monotonic()
        messages = []
        while True:
            message = ws.receive_json()
            messages.append(message)
            if message["type"] == "done":
                return messages, time.monotonic() - stopped_at


def interim(text: str) -> TranscriptEvent:
    return TranscriptEvent(type="interim", text=text)


def final(text: str) -> TranscriptEvent:
    return TranscriptEvent(type="final", text=text)


def test_finishes_after_short_settle_when_nothing_is_pending(client):
    messages, elapsed = run_session(client, [])
    assert messages == [{"type": "done"}]
    assert elapsed < 1.0  # the hard timeout is 2 s


def test_waits_for_the_final_of_an_open_interim(client):
    messages, _ = run_session(client, [(0, interim("namas")), (0.3, final("namaste"))])
    assert [m["type"] for m in messages] == ["interim", "final", "done"]


def test_final_during_the_wait_ends_on_the_short_settle(client, monkeypatch):
    monkeypatch.setattr(live, "PENDING_IDLE_SEC", 1.0)
    messages, elapsed = run_session(client, [(0, interim("namas")), (0.1, final("namaste"))])
    assert [m["type"] for m in messages] == ["interim", "final", "done"]
    assert elapsed < 0.7  # final at ~0.1 s + 0.2 s settle, not the 1 s pending limit


def test_gives_up_on_an_interim_that_is_never_finalised(client):
    messages, elapsed = run_session(client, [(0, interim("namas"))])
    assert [m["type"] for m in messages] == ["interim", "done"]
    assert 0.4 < elapsed < 1.5


def test_hard_timeout_bounds_a_provider_that_keeps_talking(client):
    script = [(0.1, interim(f"word {i}")) for i in range(100)]
    _, elapsed = run_session(client, script)
    assert 1.8 < elapsed < 3.0
