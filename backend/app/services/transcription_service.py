from app.core.exceptions import NotFoundError, ValidationError
from app.models import Transcription
from app.repositories.transcription_repository import TranscriptionRepository
from app.schemas.transcription import TranscriptionCreate, TranscriptionPage, TranscriptionRead, TranscriptionUpdate

TITLE_WORDS = 8


def _default_title(text: str) -> str:
    words = text.split()
    title = " ".join(words[:TITLE_WORDS])
    return title + ("…" if len(words) > TITLE_WORDS else "")


class TranscriptionService:
    """Business rules for transcriptions, independent of HTTP and SQL."""

    def __init__(self, repository: TranscriptionRepository, owner_id: str) -> None:
        self.repository = repository
        self.owner_id = owner_id

    def list(self, *, search: str | None, page: int, size: int) -> TranscriptionPage:
        items, total = self.repository.list(self.owner_id, search=search, offset=(page - 1) * size, limit=size)
        return TranscriptionPage(
            items=[TranscriptionRead.model_validate(item) for item in items], total=total, page=page, size=size
        )

    def get(self, transcription_id: int) -> Transcription:
        # Another owner's record is reported as missing, not forbidden, so IDs reveal nothing.
        transcription = self.repository.get(self.owner_id, transcription_id)
        if transcription is None:
            raise NotFoundError("Transcription", transcription_id)
        return transcription

    def create(self, data: TranscriptionCreate) -> Transcription:
        text = data.text.strip()
        if not text:
            raise ValidationError("Transcription text cannot be blank")
        title = (data.title or "").strip() or _default_title(text)
        return self.repository.add(
            Transcription(
                owner_id=self.owner_id,
                title=title,
                text=text,
                languages=data.languages,
                duration_sec=data.duration_sec,
            )
        )

    def update(self, transcription_id: int, data: TranscriptionUpdate) -> Transcription:
        transcription = self.get(transcription_id)
        changes = data.model_dump(exclude_unset=True)

        if "text" in changes:
            text = (changes["text"] or "").strip()
            if not text:
                raise ValidationError("Transcription text cannot be blank")
            changes["text"] = text
        if "title" in changes:
            changes["title"] = (changes["title"] or "").strip() or _default_title(changes.get("text", transcription.text))

        for field, value in changes.items():
            setattr(transcription, field, value)
        return self.repository.save(transcription)

    def delete(self, transcription_id: int) -> None:
        self.repository.delete(self.get(transcription_id))
