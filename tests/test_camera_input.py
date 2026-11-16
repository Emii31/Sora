import base64
import io
import json
import os
import re
import time

import httpx
import pytest
from PIL import Image, ImageDraw, PngImagePlugin

import camera_input


@pytest.fixture
def camera_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import app as app_module
    import auth
    import curator

    monkeypatch.setattr(auth, "_BASE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "_ADMIN_DIR", str(tmp_path / "_admin"))
    monkeypatch.setattr(app_module, "_client_mode_config", {})
    monkeypatch.setattr(curator, "start_loop_for_user", lambda *args: None)
    user = auth.get_or_create_local_single_device_user()
    return app_module.app.test_client(), {"Authorization": f"Bearer {user['token']}"}


def frame_bytes(size=(32, 24), image_format="PNG", **options):
    with Image.new("RGB", size, "blue") as frame:
        buffer = io.BytesIO()
        frame.save(buffer, format=image_format, **options)
        return buffer.getvalue()


def stub_vision_config(monkeypatch, host="127.0.0.1:11434"):
    def get_config(tier):
        assert tier == "vision"
        return {"host": host, "model": "test-vision", "api_key": "test-local", "max_tokens": 4096}

    monkeypatch.setattr(camera_input.ai_config, "get_tier_config", get_config)


def stub_transport(monkeypatch, handler):
    client = httpx.Client

    def client_factory(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(camera_input.httpx, "Client", client_factory)


def test_describes_one_frame_without_writing_chat_or_files(camera_client, monkeypatch, tmp_path):
    client, headers = camera_client
    stub_vision_config(monkeypatch, "localhost:11434")
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Comment", "private metadata")

    def provider(request):
        assert request.method == "POST"
        assert str(request.url) == "http://127.0.0.1:11434/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-local"
        payload = json.loads(request.content)
        assert payload["model"] == "test-vision"
        assert payload["max_tokens"] == 128
        data_url = payload["messages"][0]["content"][1]["image_url"]["url"]
        assert data_url.startswith("data:image/jpeg;base64,")
        frame = base64.b64decode(data_url.split(",", 1)[1])
        with Image.open(io.BytesIO(frame)) as image:
            assert image.size == (768, 384) and image.format == "JPEG"
            assert b"private metadata" not in frame
        return httpx.Response(200, json={"choices": [{"message": {"content": " A blue frame. "}}]})

    stub_transport(monkeypatch, provider)
    assert client.get("/api/chat/history", headers=headers).get_json() == []
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    response = client.post("/api/camera/describe", data=frame_bytes((1000, 500), pnginfo=metadata),
                           content_type="image/png", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"description": "A blue frame."}
    assert response.cache_control.no_store
    assert client.get("/api/chat/history", headers=headers).get_json() == []
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("headers_expected, media_type, body, status", [
    (False, "image/png", b"invalid", 401),
    (True, "application/json", b"{}", 415),
    (True, "image/jpeg", frame_bytes(), 400),
    (True, "image/png", b"invalid", 400),
    (True, "image/png", frame_bytes((4097, 1)), 400),
    (True, "image/png", b"x" * (camera_input.MAX_FRAME_BYTES + 1), 413),
])
def test_rejects_unauthenticated_or_bad_frames(camera_client, monkeypatch, headers_expected,
                                              media_type, body, status):
    def reject_provider_access(*args):
        pytest.fail("Rejected frames must not reach the vision provider")

    monkeypatch.setattr(camera_input.ai_config, "get_tier_config", reject_provider_access)
    client, headers = camera_client
    response = client.post("/api/camera/describe", data=body, content_type=media_type,
                           headers=headers if headers_expected else {})
    assert response.status_code == status


@pytest.mark.parametrize("host", ["api.openai.com", "192.168.1.5:11434", "127.example.com",
                                  "http://127.0.0.1@remote.example/v1"])
def test_remote_provider_is_refused(camera_client, monkeypatch, host):
    stub_vision_config(monkeypatch, host)
    stub_transport(monkeypatch, lambda request: pytest.fail("Camera frame would leave loopback"))
    client, headers = camera_client
    response = client.post("/api/camera/describe", data=frame_bytes(), content_type="image/png",
                           headers=headers)
    assert response.status_code == 503
    assert "loopback" in response.get_json()["error"]


@pytest.mark.parametrize("upstream", [
    httpx.Response(307, headers={"Location": "https://remote.example/vision"}),
    httpx.Response(500, json={"error": "server internal detail"}),
    httpx.Response(200, json={"choices": []}),
])
def test_provider_errors_have_no_remote_fallback(camera_client, monkeypatch, upstream):
    stub_vision_config(monkeypatch, "[::1]:11434")
    seen = []

    def respond(request):
        seen.append(str(request.url))
        return upstream

    stub_transport(monkeypatch, respond)
    client, headers = camera_client
    response = client.post("/api/camera/describe", data=frame_bytes(image_format="JPEG"),
                           content_type="image/jpeg", headers=headers)
    assert response.status_code == 503
    assert response.get_json() == {"error": "The local vision model could not describe this frame."}
    assert seen == ["http://[::1]:11434/v1/chat/completions"]


def test_busy_camera_does_not_queue_work(camera_client, monkeypatch):
    def reject_provider_access(*args):
        pytest.fail("Busy camera must not start a new request")

    monkeypatch.setattr(camera_input.ai_config, "get_tier_config", reject_provider_access)
    client, headers = camera_client
    with camera_input._vision_slot:
        response = client.post("/api/camera/describe", data=frame_bytes(), content_type="image/png",
                               headers=headers)
    assert response.status_code == 503
    assert "busy" in response.get_json()["error"]


def test_jpeg_rotation_and_exif_removal():
    exif = Image.Exif()
    exif[274] = 6  # Rotate clockwise on display.
    exif[270] = "private description"
    original = frame_bytes((30, 20), image_format="JPEG", exif=exif)
    with Image.open(io.BytesIO(camera_input._prepare_frame(original, "image/jpeg"))) as result:
        assert result.size == (20, 30)
        assert not result.getexif()


def test_real_local_vision_distinguishes_generated_frames(camera_client, monkeypatch, tmp_path):
    host = os.environ.get("SORA_TEST_VISION_URL")
    model = os.environ.get("SORA_TEST_VISION_MODEL")
    if not (host and model):
        pytest.skip("Set SORA_TEST_VISION_URL and SORA_TEST_VISION_MODEL to test an installed local model")

    config = camera_input.ai_config
    monkeypatch.setattr(config, "_cache", None)
    monkeypatch.setattr(config, "_client_cache", {})
    result = config.update_tier_config("vision", {
        "host": host,
        "model": model,
        "api_key": "ollama",
        "supports_images": True,
        "max_tokens": 96,
    })
    assert result["ok"]

    client, headers = camera_client
    assert client.get("/api/chat/history", headers=headers).get_json() == []
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    descriptions = {}
    for color, shape in (("red", "rectangle"), ("blue", "ellipse")):
        buffer = io.BytesIO()
        with Image.new("RGB", (320, 240), "white") as frame:
            draw = ImageDraw.Draw(frame)
            bounds = (60, 20, 259, 219)
            if shape == "rectangle":
                draw.rectangle(bounds, fill=color)
            else:
                draw.ellipse(bounds, fill=color)
            frame.save(buffer, format="PNG")

        started = time.perf_counter()
        response = client.post("/api/camera/describe", data=buffer.getvalue(),
                               content_type="image/png", headers=headers)
        elapsed = time.perf_counter() - started
        assert response.status_code == 200, response.get_json()
        assert response.cache_control.no_store
        description = response.get_json()["description"]
        descriptions[color] = description
        print(f"{color} {shape}: {elapsed:.2f}s · {description}")
        assert re.search(rf"\b{color}\b", description, flags=re.IGNORECASE), description

    assert descriptions["red"] != descriptions["blue"]
    assert client.get("/api/chat/history", headers=headers).get_json() == []
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
