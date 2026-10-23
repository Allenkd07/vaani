from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import TranscriptionServiceDep
from app.schemas.transcription import TranscriptionCreate, TranscriptionPage, TranscriptionRead, TranscriptionUpdate

router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])


@router.get("", response_model=TranscriptionPage)
def list_transcriptions(
    service: TranscriptionServiceDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return service.list(search=search, page=page, size=size)


@router.post("", response_model=TranscriptionRead, status_code=status.HTTP_201_CREATED)
def create_transcription(data: TranscriptionCreate, service: TranscriptionServiceDep):
    return service.create(data)


@router.get("/{transcription_id}", response_model=TranscriptionRead)
def get_transcription(transcription_id: int, service: TranscriptionServiceDep):
    return service.get(transcription_id)


@router.put("/{transcription_id}", response_model=TranscriptionRead)
def update_transcription(transcription_id: int, data: TranscriptionUpdate, service: TranscriptionServiceDep):
    return service.update(transcription_id, data)


@router.delete("/{transcription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcription(transcription_id: int, service: TranscriptionServiceDep):
    service.delete(transcription_id)
