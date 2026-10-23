"""Speech-to-text provider interface (Strategy). The WebSocket route depends only on these types."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Literal

# Audio contract between browser and providers: 16-bit little-endian PCM, mono, 16 kHz.
SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class TranscriptEvent:
    # "interim" text may still change; "final" text is a finished speech segment.
    type: Literal["interim", "final"]
    text: str
    language: str | None = None  # BCP-47 code detected by the provider, if it reports one


class SpeechToTextError(Exception):
    """Provider failure carrying a message that is safe to show users; details belong in the logs."""


class SpeechToTextSession(ABC):
    @abstractmethod
    async def send_audio(self, pcm: bytes) -> None: ...

    @abstractmethod
    async def end_audio(self) -> None:
        """No more audio will be sent; pending events are still emitted."""

    @abstractmethod
    def events(self) -> AsyncIterator[TranscriptEvent]:
        """Yield transcript events until the session is finished."""


class SpeechToTextProvider(ABC):
    @abstractmethod
    def open_session(self) -> AbstractAsyncContextManager[SpeechToTextSession]: ...
