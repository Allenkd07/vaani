from contextlib import asynccontextmanager

import pytest
from google.genai.errors import APIError
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.stt.base import SpeechToTextError, SpeechToTextProvider
from app.stt.factory import get_stt_provider
from app.stt.gemini_live import QUOTA_MESSAGE, UNAVAILABLE_MESSAGE, to_user_error
from tests.conftest import FakeSession


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (APIError(1011, "You exceeded your current quota, please check your plan and billing details."), QUOTA_MESSAGE),
        (APIError(429, {"error": {"status": "RESOURCE_EXHAUSTED"}}), QUOTA_MESSAGE),
        (Exception("server rejected WebSocket connection: HTTP 429"), QUOTA_MESSAGE),
        # Real close reason from a prepaid-billing project with no balance.
        (APIError(1011, "Your prepayment credits are depleted. Please go to AI Studio to manage billing"), QUOTA_MESSAGE),
        (APIError(1008, "API key not valid. Please pass a valid API key."), UNAVAILABLE_MESSAGE),
        (ConnectionError("network unreachable"), UNAVAILABLE_MESSAGE),
    ],
)
def test_gemini_errors_map_to_user_messages(exc, expected):
    error = to_user_error(exc)
    assert str(error) == expected
    assert "key" not in str(error).lower()


class FailingProvider(SpeechToTextProvider):
    def __init__(self, error: Exception) -> None:
        self.error = error

    @asynccontextmanager
    async def open_session(self):
        raise self.error
        yield


def receive_error(client, error: Exception) -> dict:
    app.dependency_overrides[get_stt_provider] = lambda: FailingProvider(error)
    with client.websocket_connect("/ws/transcribe") as ws:
        return ws.receive_json()


def test_provider_error_message_reaches_client(client):
    assert receive_error(client, SpeechToTextError(QUOTA_MESSAGE)) == {"type": "error", "message": QUOTA_MESSAGE}


def test_unexpected_error_details_are_not_sent_to_client(client):
    message = receive_error(client, RuntimeError("connection to 10.0.0.5:5432 refused"))
    assert message["type"] == "error"
    assert "10.0.0.5" not in message["message"]


class FailsOnCloseProvider(SpeechToTextProvider):
    @asynccontextmanager
    async def open_session(self):
        yield FakeSession()
        raise RuntimeError("provider teardown failed")


def test_error_while_closing_provider_does_not_reach_client(client):
    app.dependency_overrides[get_stt_provider] = FailsOnCloseProvider
    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "done"}
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
