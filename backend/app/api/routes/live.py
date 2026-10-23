"""WebSocket proxy: browser microphone audio -> speech-to-text provider -> live transcript.

Client protocol:
  - binary frames: raw PCM16 mono 16 kHz audio chunks
  - text frame {"type": "stop"}: no more audio; server flushes remaining text then closes
Server messages (JSON):
  - {"type": "ready"}
  - {"type": "interim" | "final", "text": "...", "language": "hi-IN" | null}
  - {"type": "error", "message": "..."}
  - {"type": "done"}
Sessions are rate limited per browser, per IP and globally; a rejected session gets an error and close code 1008.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import SessionLimiterDep, SpeechToTextProviderDep
from app.core.owner import owner_id_from_cookie
from app.core.rate_limit import RateLimitExceeded
from app.stt.base import SpeechToTextError, SpeechToTextProvider, SpeechToTextSession

logger = logging.getLogger(__name__)

router = APIRouter()

FLUSH_TIMEOUT_SEC = 10
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


async def _forward_transcripts(websocket: WebSocket, session: SpeechToTextSession) -> None:
    async for event in session.events():
        await websocket.send_json({"type": event.type, "text": event.text, "language": event.language})


def _client_keys(websocket: WebSocket) -> dict[str, str]:
    keys = {}
    if owner_id := owner_id_from_cookie(websocket):
        keys["owner"] = f"owner:{owner_id}"
    if websocket.client:
        keys["ip"] = f"ip:{websocket.client.host}"
    return keys


@router.websocket("/ws/transcribe")
async def transcribe(websocket: WebSocket, provider: SpeechToTextProviderDep, limiter: SessionLimiterDep) -> None:
    await websocket.accept()
    try:
        with limiter.hold(_client_keys(websocket)):
            await _run_session(websocket, provider)
    except RateLimitExceeded as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1008)


async def _run_session(websocket: WebSocket, provider: SpeechToTextProvider) -> None:
    try:
        async with provider.open_session() as session:
            await websocket.send_json({"type": "ready"})
            pump = asyncio.create_task(_pump_client_audio(websocket, session))
            forwarder = asyncio.create_task(_forward_transcripts(websocket, session))
            try:
                done, _ = await asyncio.wait({pump, forwarder}, return_when=asyncio.FIRST_COMPLETED)
                if pump in done:
                    pump.result()  # re-raises a client disconnect
                    # Client sent stop: wait for the provider's last segment.
                    await asyncio.wait_for(forwarder, timeout=FLUSH_TIMEOUT_SEC)
                else:
                    forwarder.result()  # re-raises a provider error
            except TimeoutError:
                logger.warning("Timed out waiting for final transcript")
            finally:
                pump.cancel()
                forwarder.cancel()
        await websocket.send_json({"type": "done"})
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except SpeechToTextError as exc:
        await _send_error(websocket, str(exc))
    except Exception:
        # Raw exception text can leak internals, so the client only gets a generic message.
        logger.exception("Live transcription failed")
        await _send_error(websocket, GENERIC_ERROR_MESSAGE)


async def _send_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_json({"type": "error", "message": message})
        await websocket.close(code=1011)
    except Exception:
        pass  # the client may already be gone
