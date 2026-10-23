from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Transcription


class TranscriptionRepository:
    """Database access for transcriptions. Every read is scoped to one owner."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, owner_id: str, *, search: str | None, offset: int, limit: int) -> tuple[list[Transcription], int]:
        query = select(Transcription).where(Transcription.owner_id == owner_id)
        if search:
            pattern = f"%{search}%"
            query = query.where(or_(Transcription.title.ilike(pattern), Transcription.text.ilike(pattern)))

        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = self.db.scalars(
            query.order_by(Transcription.created_at.desc(), Transcription.id.desc()).offset(offset).limit(limit)
        ).all()
        return list(items), total

    def get(self, owner_id: str, transcription_id: int) -> Transcription | None:
        return self.db.scalar(
            select(Transcription).where(Transcription.id == transcription_id, Transcription.owner_id == owner_id)
        )

    def add(self, transcription: Transcription) -> Transcription:
        self.db.add(transcription)
        self.db.commit()
        self.db.refresh(transcription)
        return transcription

    def save(self, transcription: Transcription) -> Transcription:
        self.db.commit()
        self.db.refresh(transcription)
        return transcription

    def delete(self, transcription: Transcription) -> None:
        self.db.delete(transcription)
        self.db.commit()
