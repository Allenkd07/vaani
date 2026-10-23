from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Comma-separated ISO 639 primary language subtags, e.g. "hi,en,ta".
LANGUAGES_PATTERN = r"^[a-z]{2,3}(,[a-z]{2,3})*$"


class TranscriptionBase(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    languages: str | None = Field(default=None, max_length=50, pattern=LANGUAGES_PATTERN)
    duration_sec: int | None = Field(default=None, ge=0)


class TranscriptionCreate(TranscriptionBase):
    text: str = Field(min_length=1)


class TranscriptionUpdate(TranscriptionBase):
    text: str | None = Field(default=None, min_length=1)


class TranscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    text: str
    languages: str | None
    duration_sec: int | None
    created_at: datetime
    updated_at: datetime


class TranscriptionPage(BaseModel):
    items: list[TranscriptionRead]
    total: int
    page: int
    size: int
