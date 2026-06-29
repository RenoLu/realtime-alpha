import pytest

from realtime_alpha.llm import AnthropicClient, MockClient, ModelError, extract_json


def test_mock_client_returns_canned():
    assert MockClient(canned="hello").complete(system="s", prompt="p") == "hello"


def test_mock_client_uses_responder():
    c = MockClient(responder=lambda system, prompt: f"{system}|{prompt}")
    assert c.complete(system="A", prompt="B") == "A|B"


def test_extract_json_from_messy_text():
    assert extract_json('noise {"yhat": 0.5, "confidence": 0.6} tail') == {
        "yhat": 0.5,
        "confidence": 0.6,
    }


def test_extract_json_raises_without_object():
    with pytest.raises(ModelError):
        extract_json("no json here")


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._p = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._p


class _FakeHttp:
    def __init__(self, payload: dict) -> None:
        self._p = payload
        self.calls: list[dict] = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResp(self._p)


def test_anthropic_client_builds_request_and_parses_text():
    fake = _FakeHttp({"content": [{"type": "text", "text": "hi there"}]})
    c = AnthropicClient("k", model="claude-haiku-4-5", client=fake)
    out = c.complete(system="sys", prompt="usr", max_tokens=128)
    assert out == "hi there"
    req = fake.calls[0]
    assert req["url"].endswith("/v1/messages")
    assert req["headers"]["x-api-key"] == "k"
    assert req["json"]["model"] == "claude-haiku-4-5"
    assert req["json"]["system"] == "sys"
    assert req["json"]["messages"] == [{"role": "user", "content": "usr"}]
    assert "thinking" not in req["json"]  # Haiku takes no thinking param


def test_anthropic_client_sets_adaptive_thinking_when_requested():
    fake = _FakeHttp({"content": [{"type": "text", "text": "ok"}]})
    AnthropicClient("k", client=fake).complete(system="s", prompt="p", thinking=True)
    assert fake.calls[0]["json"]["thinking"] == {"type": "adaptive"}


def test_anthropic_client_requires_api_key():
    with pytest.raises(ModelError):
        AnthropicClient("")
