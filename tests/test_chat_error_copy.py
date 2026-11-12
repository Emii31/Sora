from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chat_error_copy_hides_internal_ai_tier_wording():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert "friendlyChatErrorMessage" in html
    assert "Sora is not configured with AI models yet" in html
    assert "Vision, Chat, and Memory models" in html
    chat_send_block = html[html.index("async function sendCompanionMessage"):html.index("let _companionLastMsgId")]
    assert "friendlyChatErrorMessage" in chat_send_block
    assert "Error:" not in chat_send_block
    assert "Network error:" not in chat_send_block


def test_backend_missing_model_copy_does_not_use_admin_ui_language():
    prompt_py = (ROOT / "prompt.py").read_text(encoding="utf-8")
    memory_prompts_py = (ROOT / "memory_prompts.py").read_text(encoding="utf-8")

    user_facing_blocks = prompt_py[prompt_py.index("def _get_ai_runtime_or_raise"):prompt_py.index("def _get_chat_model")]
    user_facing_blocks += "\n" + memory_prompts_py[memory_prompts_py.index("def call_screen_observation"):memory_prompts_py.index("model = runtime")]

    assert "Model configuration incomplete" in user_facing_blocks
    assert "Model settings page in Sora" in user_facing_blocks
    assert "AI tier" not in user_facing_blocks
    assert "Admin UI" not in user_facing_blocks
    assert "Vision tier API key not set" not in user_facing_blocks


def test_backend_friendly_chat_error_mapping_hides_internal_terms():
    import core

    samples = [
        RuntimeError("Model configuration incomplete: Chat model missing service URL. Please fill in the service URL, model name, and API Key in the Model settings page in Sora."),
        RuntimeError("AI tier 'chat' API Key is not set. Configure via Admin UI > AI 配置."),
        TimeoutError("API timeout after 30s"),
        ConnectionError("connection refused"),
        RuntimeError("unexpected provider failure"),
    ]

    replies = [core._friendly_chat_generation_error(exc) for exc in samples]

    assert "I haven't configured my models yet" in replies[0]
    assert "I haven't configured my models yet" in replies[1]
    assert "couldn't connect to the model service" in replies[2]
    assert "couldn't connect to the model service" in replies[3]
    assert "small issue" in replies[4]
    for reply in replies:
        lowered = reply.lower()
        assert "ai tier" not in lowered
        assert "admin ui" not in lowered
        assert "api timeout" not in lowered


def test_api_companion_chat_blank_input_returns_400(monkeypatch):
    import app as app_module
    import auth

    def _fake_check_request(req=None):
        return None

    monkeypatch.setattr(auth, "check_request", _fake_check_request)
    client = app_module.app.test_client()
    response = client.post("/api/companion/chat", json={"text": "   "})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "Please enter a message"