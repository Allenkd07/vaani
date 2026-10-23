"""WebSocket proxy: browser microphone audio -> speech-to-text provider -> live transcript.

Client protocol:
  - binary frames: raw PCM16 mono 16 kHz audio chunks
  - text frame {"type": "stop"}: no more audio; server flushes remaining text then closes.
    After stop the server ends once the provider goes quiet: SETTLE_SEC if the last segment is final,
    PENDING_IDLE_SEC if an interim is still open, and never later than FLUSH_TIMEOUT_SEC.
Server messages (JSON):
  - {"type": "ready"}
  - {"type": "interim" | "final", "text": "...", "language": "hi-IN" | null}
  - {"type": "error", "message": "..."}
  - {"type": "done"}
Sessions are rate limited per browser, per IP, globally and per day; a rejected session gets an error and close code 1008.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.api.deps import DailyQuotaDep, SessionLimiterDep, SpeechToTextProviderDep
from app.core.owner import owner_id_from_cookie
from app.core.rate_limit import RateLimitExceeded
from app.stt.base import SpeechToTextError, SpeechToTextProvider, SpeechToTextSession

logger = logging.getLogger(__name__)

router = APIRouter()

FLUSH_TIMEOUT_SEC = 10
SETTLE_SEC = 1.5
PENDING_IDLE_SEC = 3.0
GENERIC_ERROR_MESSAGE = "Something went wrong during transcription. Please try again."


async def _pump_client_audio(websocket: WebSocket, session: SpeechToTextSession) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
        if message.get("bytes"):
            await session.send_audio(message["bytes"])
        elif message.get("text") and json.loads(message["text"]).get("type") == "stop":
            await session.end_audio()
            return


@dataclass
class _Progress:
    last_event_at: float = field(default_factory=time.monotonic)
    interim_pending: bool = False
    changed: asyncio.Event = field(default_factory=asyncio.Event)


async def _forward_transcripts(websocket: WebSocket, session: SpeechToTextSession, progress: _Progress) -> None:
    async for event in session.events():
        await websocket.send_json({"type": event.type, "text": event.text, "language": event.language})
        progress.last_event_at = time.monotonic()
        progress.interim_pending = event.type == "interim"
        progress.changed.set()


async def _settle(forwarder: asyncio.Task, progress: _Progress) -> None:
    """After stop, waits for the provider's remaining text until it goes quiet.

    Waiting for the provider to end its turn is not enough: if the last segment was finalised before
    stop, no further turn arrives and the session would idle until the hard timeout.
    """
    stopped_at = time.monotonic()
    while not forwarder.done():
        now = time.monotonic()
        idle_limit = PENDING_IDLE_SEC if progress.interim_pending else SETTLE_SEC
        remaining = min(
            idle_limit - (now - max(progress.last_event_at, stopped_at)),
            FLUSH_TIMEOUT_SEC - (now - stopped_at),
        )
        if remaining <= 0:
            if progress.interim_pending:
                logger.info("Provider left an interim segment unfinalised; the client keeps it")
            return
        # Wake on new events too: a final arriving during the wait shortens the remaining idle limit.
        progress.changed.clear()
        changed = asyncio.create_task(progress.changed.wait())
        await asyncio.wait({forwarder, changed}, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
        changed.cancel()
    forwarder.result()  # re-raises a provider error


def _client_keys(websocket: WebSocket) -> dict[str, str]:
    keys = {}
    if owner_id := owner_id_from_cookie(websocket):
        keys["owner"] = f"owner:{owner_id}"
    if websocket.client:
        keys["ip"] = f"ip:{websocket.client.host}"
    return keys


@router.websocket("/ws/transcribe")
async def transcribe(
    websocket: WebSocket, provider: SpeechToTextProviderDep, limiter: SessionLimiterDep, quota: DailyQuotaDep
) -> None:
    await websocket.accept()
    try:
        with limiter.hold(_client_keys(websocket)):
            # Counted only after the per-client checks pass, so rejected attempts don't use up the day.
            await run_in_threadpool(quota.consume)
            await _run_session(websocket, provider)
    except RateLimitExceeded as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1008)


async def _run_session(websocket: WebSocket, provider: SpeechToTextProvider) -> None:
    done_sent = False
    try:
        async with provider.open_session() as session:
            await websocket.send_json({"type": "ready"})
            progress = _Progress()
            pump = asyncio.create_task(_pump_client_audio(websocket, session))
            forwarder = asyncio.create_task(_forward_transcripts(websocket, session, progress))
            try:
                done, _ = await asyncio.wait({pump, forwarder}, return_when=asyncio.FIRST_COMPLETED)
                if pump in done:
                    pump.result()  # re-raises a client disconnect
                    await _settle(forwarder, progress)
                else:
                    forwarder.result()  # re-raises a provider error
            finally:
                pump.cancel()
                forwarder.cancel()
            # Sent before the provider session closes, so the client doesn't wait on that teardown.
            await websocket.send_json({"type": "done"})
            done_sent = True
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as exc:
        if done_sent:
            # The client already has its full transcript; a failure while closing the provider is only logged.
            logger.exception("Error closing the provider session")
            await websocket.close()
        elif isinstance(exc, SpeechToTextError):
            await _send_error(websocket, str(exc))
        else:
            # Raw exception text can leak internals, so the client only gets a generic message.
            logger.exception("Live transcription failed")
            await _send_error(websocket, GENERIC_ERROR_MESSAGE)


async def _send_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_json({"type": "error", "message": message})
        await websocket.close(code=1011)
    except Exception:
        pass  # the client may already be gone
