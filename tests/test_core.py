import json
import time
import urllib.request

import pytest

from wurubururu import ai, config
from wurubururu.buttons import GestureDetector
from wurubururu.device import MockDevice
from wurubururu.engine import Alert, Engine
from wurubururu.leds import BUILTIN, LedPlayer, parse_pattern
from wurubururu.sources.sitewatch import SiteWatchSource


def feed(det, seq):
    """seq: [(값, 시각)] → 발생한 이벤트 목록"""
    out = []
    for raw, t in seq:
        out += det.feed(raw, t)
    return out


def press(det, bit, t0, hold, step=0.02):
    seq, t = [], t0
    while t < t0 + hold:
        seq.append((bit, t)); t += step
    return seq, t


def test_default_config_is_valid_and_complete():
    cfg = config.load(path=config.HOME / "does-not-exist.toml")
    assert cfg["ai"]["provider"] in ai.PROVIDERS
    for name in cfg["patterns"].values():
        parse_pattern(name)
    assert set(cfg["ai"]) >= {"gemini", "claude", "grok", "claude_cli"}


def test_original_patterns_match_reverse_engineered_bytes():
    assert BUILTIN["left"] == [(0x80, 5), (0x40, 5)]
    assert BUILTIN["right"] == [(0x10, 5), (0x20, 5)]
    assert BUILTIN["both"] == [(0x90, 5), (0x60, 5)]


def test_click_long_double():
    det = GestureDetector()
    det.feed(0, 0.0)
    seq, t = press(det, 0x01, 0.1, 0.1)
    idle = [(0, t + i * 0.02) for i in range(30)]
    assert feed(det, seq + idle) == [("left", "click")]

    det = GestureDetector(); det.feed(0, 0.0)
    seq, t = press(det, 0x04, 0.1, 1.0)
    assert feed(det, seq + [(0, t), (0, t + 0.02), (0, t + 0.5)]) == [("mute", "long")]

    det = GestureDetector(); det.feed(0, 0.0)
    a, t = press(det, 0x02, 0.1, 0.08)
    gap = [(0, t), (0, t + 0.02), (0, t + 0.04)]
    b, t2 = press(det, 0x02, t + 0.1, 0.08)
    tail = [(0, t2 + i * 0.02) for i in range(30)]
    assert feed(det, a + gap + b + tail) == [("right", "double")]


def test_buttons_work_when_idle_level_is_high():
    """눌렀을 때 비트가 0이 되는 배선이어도 동작해야 한다."""
    det = GestureDetector()
    det.feed(0x07, 0.0)
    seq, t = press(det, 0x06, 0.1, 0.1)      # bit0 이 0으로 떨어짐 = 왼발 누름
    idle = [(0x07, t + i * 0.02) for i in range(30)]
    assert feed(det, seq + idle) == [("left", "click")]


def test_led_player_base_and_flash():
    dev = MockDevice()
    leds = LedPlayer(dev)
    leds.set_base([[0x80, 1], [0x40, 1]])
    time.sleep(0.45)
    assert {0x80, 0x40} <= set(dev.history)
    leds.set_base(None)
    time.sleep(0.25)
    assert dev.leds == 0
    leds.flash([[0x10, 1]], repeat=2)
    time.sleep(0.4)
    assert dev.history.count(0x10) == 2 and dev.leds == 0
    leds.stop()


class FakeAI(ai.Provider):
    name = "fake"
    def __init__(self): super().__init__({}, {})
    def complete(self, system, prompt):
        if "분류기" in system:
            return '설명 {"priority": "urgent", "summary": "오늘 회신 필요"} 끝'
        return "요약문"


def make_engine(**over):
    cfg = config.load(path=config.HOME / "does-not-exist.toml")
    cfg.update(over)
    said, opened = [], []
    eng = Engine(cfg, MockDevice(), FakeAI(), speak=lambda t, c: said.append(t), open_url=opened.append,
                 play_sound=lambda path: opened.append(f"sound:{path}") or True)
    return eng, said, opened


def test_intro_plays_once_at_start_and_missing_file_is_skipped(tmp_path):
    eng, _, opened = make_engine(intro={"enabled": True, "file": "~/x/intro.mp3"})
    try:
        eng.start()
        assert opened == ["sound:~/x/intro.mp3"]
    finally:
        eng.stop()
    from wurubururu import actions
    assert actions.play_sound(str(tmp_path / "none.mp3")) is False


def test_engine_alert_flow_and_buttons():
    eng, said, opened = make_engine()
    try:
        assert eng.post(Alert("mail", "김씨: 견적", url="https://mail.google.com/x", key="m1"))
        assert eng.post(Alert("site", "사이트 응답 없음", priority="urgent", url="https://a.example", key="u"))
        assert not eng.post(Alert("mail", "김씨: 견적", key="m1")), "같은 사건은 한 번만"
        assert not eng.post(Alert("mail", "광고", priority="ignore"))
        assert eng.top().kind == "site"
        assert eng.pattern_for(eng.top()) == "alarm"
        eng.on_button("left", "click")
        assert opened == ["https://a.example"] and eng.top().kind == "mail"
        eng.on_button("right", "click")
        assert said[-1] == "김씨: 견적"
        eng.on_button("mute", "click")
        assert eng.top() is None
        assert not eng.post(Alert("mail", "김씨: 견적", key="m1")), "확인한 알림은 다시 울리지 않음"
        eng.resolve("site", "u")
        assert eng.post(Alert("site", "또 응답 없음", priority="urgent", key="u")), "복구 후 재발은 다시 알림"
    finally:
        eng.stop()


def test_dnd_hides_normal_but_not_urgent():
    eng, said, _ = make_engine()
    try:
        eng.on_button("mute", "long")
        assert eng.dnd
        eng.post(Alert("mail", "보통 메일", key="a"))
        time.sleep(0.15)
        assert eng.leds._base is None
        eng.post(Alert("site", "장애", priority="urgent", key="b"))
        assert eng.leds._base == BUILTIN["alarm"]
    finally:
        eng.stop()


def test_triage_privacy_and_parsing():
    eng, _, _ = make_engine()
    seen = {}
    class Spy(FakeAI):
        def triage(self, sender, subject, snippet=""):
            seen["snippet"] = snippet
            return super().triage(sender, subject, snippet)
    eng.provider = Spy()
    try:
        v = eng.triage_mail("a@b.c", "제목", "비밀 본문")
        assert v == {"priority": "urgent", "summary": "오늘 회신 필요"}
        assert seen["snippet"] == "", "기본값(headers)에서는 본문을 AI로 보내지 않는다"
    finally:
        eng.stop()
    assert ai.parse_triage("엉뚱한 답")["priority"] == "normal"
    assert ai.parse_triage('{"priority":"delete everything"}')["priority"] == "normal"


@pytest.mark.parametrize("name,response,expect_url,expect_header", [
    ("gemini", {"candidates": [{"content": {"parts": [{"text": "안녕"}]}}]},
     "generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent", "X-goog-api-key"),
    ("claude", {"content": [{"type": "text", "text": "안녕"}]}, "api.anthropic.com/v1/messages", "X-api-key"),
    ("grok", {"choices": [{"message": {"content": "안녕"}}]}, "api.x.ai/v1/chat/completions", "Authorization"),
])
def test_providers_build_correct_requests(monkeypatch, name, response, expect_url, expect_header):
    captured = {}
    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(response).encode()
    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data)
        return Resp()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    cfg = config.load(path=config.HOME / "does-not-exist.toml")["ai"]
    cfg["provider"] = name
    cfg[name]["api_key"] = "k"
    p = ai.get_provider(cfg)
    assert p.complete("sys", "hi") == "안녕"
    assert expect_url in captured["url"]
    assert expect_header in captured["headers"]


def test_provider_none_and_missing_key(monkeypatch):
    assert ai.get_provider({"provider": "none"}) is None
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(ai.AIError):
        ai.get_provider({"provider": "grok", "grok": {}}).complete("s", "p")
    with pytest.raises(ai.AIError):
        ai.get_provider({"provider": "chatgpt"})


def test_sitewatch_alerts_after_threshold_and_recovers():
    eng, said, _ = make_engine()
    state = {"down": True}
    src = SiteWatchSource({"urls": ["https://a.example"], "fail_threshold": 2},
                          checker=lambda u: "timeout" if state["down"] else None)
    try:
        src.poll(eng); assert eng.top() is None
        src.poll(eng); assert eng.top().kind == "site"
        src.poll(eng); assert len(eng.alerts) == 1
        state["down"] = False
        src.poll(eng); assert eng.top() is None
    finally:
        eng.stop()


def test_web_api_requires_token(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr(config, "TOKEN_PATH", tmp_path / "web_token")
    from wurubururu import web
    eng, _, _ = make_engine()
    server = web.start(eng, 0)
    port = server.server_address[1]
    def call(path, body=None, token=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-Wurubururu-Token": token} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, {}
    try:
        assert call("/api/status")[0] == 200
        assert call("/api/notify", {"title": "x"})[0] == 401
        assert call("/api/notify", {"title": "빌드 끝"}, config.web_token()) == (200, {"ok": True})
        assert eng.top().title == "빌드 끝"
        assert call("/api/config", {"text": "this is = not [valid"}, config.web_token())[0] == 400
    finally:
        server.shutdown(); eng.stop()
