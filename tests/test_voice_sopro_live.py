import io
import json
from threading import Event

import pytest

from voice_sopro_live import SoproStream


@pytest.mark.parametrize(
    "events, error",
    [
        ([{"type": "speech.audio.delta", "audio": "ABA="}, {"type": "speech.audio.done"}], None),
        ([{"type": "speech.audio.delta", "audio": "ABA="}], RuntimeError),
        ([{"type": "speech.audio.done"}], RuntimeError),
        ([{"type": "speech.audio.delta", "audio": "AA=="}], ValueError),
    ],
)
def test_sopro_only_confirms_reply_after_complete_pcm(monkeypatch, events, error):
    class Connection:
        def request(self, method, path, body, headers):
            payload = json.loads(body)
            assert (method, path) == ("POST", "/v1/audio/speech")
            assert payload["input"] == "Hello"
            assert payload["voice_ref"] == "/reference.wav"
            assert "wav" not in payload

        def getresponse(self):
            response = io.BytesIO(b"".join(
                b"data: " + json.dumps(event).encode() + b"\n\n" for event in events
            ))
            response.status = 200
            return response

        def close(self):
            pass

    monkeypatch.setattr("voice_sopro_live.http.client.HTTPConnection", lambda *a, **k: Connection())
    stream = SoproStream("http://127.0.0.1:4321/v1/audio/speech", Event(), "/reference.wav")
    delivery = stream.events(b"microphone recording", spoken_text="Hello")
    if error:
        with pytest.raises(error):
            list(delivery)
    else:
        assert list(delivery) == [("audio", b"\x00\x10"), ("text", "Hello")]
    assert stream.connection is None
