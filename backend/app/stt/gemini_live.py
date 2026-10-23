import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from google import genai
from google.genai import types

from app.stt.base import SAMPLE_RATE, SpeechToTextError, SpeechToTextProvider, SpeechToTextSession, TranscriptEvent

logger = logging.getLogger(__name__)

QUOTA_MESSAGE = "Vaani has reached its transcription limit for now. Please try again later."
UNAVAILABLE_MESSAGE = "Transcription is unavailable right now. Please try again in a moment."

# Exhausted quota and depleted prepaid billing credits both mean "over the limit" to a user.
_QUOTA_PATTERN = re.compile(r"\b429\b|resource_exhausted|quota|rate limit|credits are depleted")


def to_user_error(exc: Exception) -> SpeechToTextError:
    """Maps a Gemini failure to a user-safe message.

    Live API errors are APIError whose code is the WebSocket close code and whose text is the close reason;
    handshake failures are websockets errors mentioning the HTTP status. Auth and config problems get the
    generic message: they are for the operator, not the user.
    """
    text = f"{getattr(exc, 'code', '')} {getattr(exc, 'status', '')} {exc}".lower()
    logger.warning("Gemini Live error: %s", exc)
    return SpeechToTextError(QUOTA_MESSAGE if _QUOTA_PATTERN.search(text) else UNAVAILABLE_MESSAGE)


class GeminiLiveSession(SpeechToTextSession):
    """Adapts a Gemini Live session to SpeechToTextSession."""

    def __init__(self, session) -> None:
        self._session = session
        self._audio_ended = False

    async def send_audio(self, pcm: bytes) -> None:
        try:
            await self._session.send_realtime_input(
                audio=types.Blob(data=pcm, mime_type=f"audio/pcm;rate={SAMPLE_RATE}")
            )
        except Exception as exc:
            raise to_user_error(exc) from exc

    async def end_audio(self) -> None:
        self._audio_ended = True
        try:
            await self._session.send_realtime_input(audio_stream_end=True)
        except Exception as exc:
            raise to_user_error(exc) from exc

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        try:
            # receive() ends after each server turn; re-enter until audio has ended and the last turn is flushed.
            while True:
                received = False
                async for message in self._session.receive():
                    received = True
                    content = message.server_content
                    if content is None:
                        continue
                    interim = content.interim_input_transcription
                    if interim and interim.text:
                        yield TranscriptEvent(type="interim", text=interim.text, language=interim.language_code)
                    final = content.input_transcription
                    if final and final.text:
                        logger.info("Final segment language: %s", final.language_code)
                        yield TranscriptEvent(type="final", text=final.text, language=final.language_code)
                if self._audio_ended or not received:  # empty pass = server closed the session
                    return
        except Exception as exc:
            raise to_user_error(exc) from exc


class GeminiLiveProvider(SpeechToTextProvider):
    def __init__(self, *, api_key: str, model: str, language_codes: list[str], mode: str) -> None:
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            input_audio_transcription=types.AudioTranscriptionConfig(language_codes=language_codes, mode=mode),
        )

    @asynccontextmanager
    async def open_session(self) -> AsyncIterator[GeminiLiveSession]:
        connected = False
        try:
            async with self._client.aio.live.connect(model=self._model, config=self._config) as session:
                connected = True
                yield GeminiLiveSession(session)
        except Exception as exc:
            # Only connection failures are translated; errors raised by the caller's block propagate unchanged.
            if connected:
                raise
            raise to_user_error(exc) from exc
