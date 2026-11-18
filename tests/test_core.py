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


def test_button_bits_match_hardware():
    """기기 확인 결과: 왼발 0x02, 오른발 0x01, 머리 0x04."""
    cfg = config.load(path=config.HOME / "does-not-exist.toml")["device"]["buttons"]
    assert (cfg["left"], cfg["right"], cfg["mute"]) == (0x02, 0x01, 0x04)
    assert GestureDetector().bits == {"left": 0x02, "right": 0x01, "mute": 0x04}


def test_no_builtin_pattern_lights_both_colors_on_one_ear():
    from wurubururu.leds import ear_conflict
    for name, steps in BUILTIN.items():
        assert not any(ear_conflict(v) for v, _ in steps), name


def test_color_meaning_matches_hardware():
    """기기 확인 결과: 0x80 왼빨, 0x40 왼초, 0x20 오빨, 0x10 오초. 급함은 빨강만, 보통은 초록만."""
    red, green = 0xA0, 0x50
    for name in ("urgent", "alarm", "red_left", "red_right"):
        assert all(v & green == 0 for v, _ in BUILTIN[name]), name
    for name in ("green_left", "green_right", "pulse", "solid_left", "solid_right"):
        assert all(v & red == 0 for v, _ in BUILTIN[name]), name


def test_click_long_double():
    det = GestureDetector()
    det.feed(0, 0.0)
    seq, t = press(det, 0x02, 0.1, 0.1)
    idle = [(0, t + i * 0.02) for i in range(30)]
    assert feed(det, seq + idle) == [("left", "click")]

    det = GestureDetector(); det.feed(0, 0.0)
    seq, t = press(det, 0x04, 0.1, 1.0)
    assert feed(det, seq + [(0, t), (0, t + 0.02), (0, t + 0.5)]) == [("mute", "long")]

    det = GestureDetector(); det.feed(0, 0.0)
    a, t = press(det, 0x01, 0.1, 0.08)
    gap = [(0, t + i * 0.02) for i in range(6)]          # 0.12초 뗌 (실제 읽기 간격 0.02초)
    b, t2 = press(det, 0x01, t + 0.12, 0.08)
    tail = [(0, t2 + i * 0.02) for i in range(30)]
    assert feed(det, a + gap + b + tail) == [("right", "double")]


def test_flaky_contact_during_press_is_one_click():
    """노화된 버튼: 누르는 도중 접촉이 1~2회씩 끊겨도 클릭 한 번으로 본다."""
    det = GestureDetector()
    det.feed(0, 0.0)
    pattern = [0x02, 0x02, 0, 0x02, 0x02, 0, 0, 0x02, 0x02, 0x02, 0, 0x02]
    seq = [(v, 0.1 + i * 0.02) for i, v in enumerate(pattern)]
    t = seq[-1][1]
    tail = [(0, t + 0.02 * (i + 1)) for i in range(30)]
    assert feed(det, seq + tail) == [("left", "click")]


def test_single_read_press_is_recognized():
    """꾹 눌렀을 때 아주 짧게만 잡혀도 놓치지 않는다."""
    det = GestureDetector()
    det.feed(0, 0.0)
    assert feed(det, [(0x04, 0.1)] + [(0, 0.12 + i * 0.02) for i in range(30)]) == [("mute", "click")]


def test_buttons_work_when_idle_level_is_high():
    """눌렀을 때 비트가 0이 되는 배선이어도 동작해야 한다."""
    det = GestureDetector()
    det.feed(0x07, 0.0)
    seq, t = press(det, 0x05, 0.1, 0.1)      # bit1 이 0으로 떨어짐 = 왼발 누름
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
    eng, _, opened = make_engine(intro={"enabled": True, "file": "~/x/intro.mp3", "delay": 0.05})
    try:
        eng.start()
        assert opened == [], "초기화 직후 바로 틀지 않는다"
        time.sleep(0.2)
        assert opened == ["sound:~/x/intro.mp3"]
    finally:
        eng.stop()
    from pathlib import Path
    from wurubururu import actions
    assert actions.play_sound(str(tmp_path / "none.mp3")) is False
    assert Path(actions.bundled_intro()).is_file()
    eng, _, opened = make_engine(intro={"enabled": True, "file": "", "delay": 0})
    try:
        eng.start()
        time.sleep(0.1)
        assert opened == [f"sound:{actions.bundled_intro()}"], "경로를 비우면 기본 인트로"
    finally:
        eng.stop()


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
    def fake_urlopen(req, timeout=0, context=None):
        captured["context"] = context
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
    assert captured["context"] is not None, "앱 안에서도 인증서를 확인할 수 있게 certifi 묶음을 써야 한다"


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


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr(config, "TOKEN_PATH", tmp_path / "web_token")
    from wurubururu import keystore
    monkeypatch.setattr(keystore, "_keyring", lambda: None)   # 시험 중에는 실제 키체인을 건드리지 않음
    cfgtext = 'intro = { enabled = false }\n[gmail]\nenabled = false\n[calendar]\nenabled = false\n[ai]\nprovider = "none"\n'
    (tmp_path / "config.toml").write_text(cfgtext, encoding="utf-8")
    return tmp_path


def start_app(home):
    from wurubururu import web
    from wurubururu.app import App
    app = App(mock=True)
    app.start_engine(greet=False)
    server = web.start(app, 0)
    port = server.server_address[1]
    def call(path, body=None, token=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-Wurubururu-Token": token} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
    app.server = server
    return app, call


def test_web_api_requires_token(home):
    app, call = start_app(home)
    tok = config.web_token()
    try:
        assert call("/api/status")[0] == 200
        assert call("/api/notify", {"title": "x"})[0] == 401
        assert call("/api/notify", {"title": "빌드 끝"}, tok) == (200, {"ok": True})
        assert app.engine.top().title == "빌드 끝"
        assert call("/api/config", {"text": "this is = not [valid"}, tok)[0] == 400
    finally:
        app.shutdown()


def test_settings_save_applies_without_restart_and_keeps_alerts(home):
    app, call = start_app(home)
    tok = config.web_token()
    try:
        call("/api/notify", {"title": "남아 있어야 할 알림"}, tok)
        code, s = call("/api/settings")
        assert code == 200 and s["cfg"]["ai"]["provider"] == "none"
        cfg = s["cfg"]
        cfg["buttons"]["left.click"] = "briefing"
        cfg["sitewatch"]["urls"] = ["https://example.com"]
        cfg["patterns"]["mail.normal"] = "pulse"
        assert call("/api/settings", {"cfg": cfg}, tok)[0] == 200
        assert app.engine.cfg["buttons"]["left.click"] == "briefing", "재시작 없이 적용"
        assert app.engine.top().title == "남아 있어야 할 알림", "확인하지 않은 알림은 유지"
        saved = (home / "config.toml").read_text(encoding="utf-8")
        assert "briefing" in saved and "example.com" in saved
        assert "gemini-3.5" not in saved, "기본값과 같은 항목은 저장하지 않는다"
        import tomllib
        tomllib.loads(saved)
    finally:
        app.shutdown()


def test_secret_goes_to_store_not_config(home):
    app, call = start_app(home)
    tok = config.web_token()
    try:
        assert call("/api/secret", {"name": "ai.gemini", "value": "abc123"}, tok)[1]["where"] == "file"
        assert call("/api/settings")[1]["secrets"]["ai.gemini"] is True
        assert "abc123" not in (home / "config.toml").read_text(encoding="utf-8")
        assert call("/api/secret", {"name": "../../etc", "value": "x"}, tok)[0] == 400
        from wurubururu import ai
        assert ai._key({}, "gemini") == "abc123"
    finally:
        app.shutdown()


def test_google_client_file_validation(home):
    app, call = start_app(home)
    tok = config.web_token()
    try:
        assert call("/api/google/client", {"text": "{}"}, tok)[0] == 400
        assert call("/api/google/client", {"text": '{"web": {}}'}, tok)[0] == 400
        ok = '{"installed": {"client_id": "x", "client_secret": "y"}}'
        assert call("/api/google/client", {"text": ok}, tok)[0] == 200
        assert call("/api/settings")[1]["google"]["client_secret"] is True
    finally:
        app.shutdown()


def test_toml_writer_roundtrip():
    import tomllib
    from wurubururu.tomlwrite import diff, dumps
    data = {"a": 1, "b": {"c": "따옴표\"와 \\역슬래시\n줄바꿈", "d": [1, 2], "mail.urgent": "x",
                         "e": {"f": True, "g": 1.5}},
            "radio": {"stations": [{"name": "방송", "url": "https://x"}]}, "empty": {}}
    assert tomllib.loads(dumps(data)) == data
    assert diff({"a": 1, "b": {"c": 2, "d": 3}}, {"a": 1, "b": {"c": 2, "d": 4}}) == {"b": {"d": 3}}


def test_auto_device_reconnects():
    from wurubururu.device import AutoDevice, DeviceError, MockDevice
    state = {"plugged": False}
    def factory():
        if not state["plugged"]:
            raise DeviceError("없음")
        return MockDevice()
    dev = AutoDevice(factory, retry=0)
    dev.init()
    assert not dev.connected
    with pytest.raises(DeviceError):
        dev.write_leds(0x40)
    state["plugged"] = True
    dev.write_leds(0x40)
    assert dev.connected


def test_quit_from_settings_page_stops_app(home):
    app, call = start_app(home)
    try:
        assert call("/api/quit", {}, config.web_token())[0] == 200
        assert app.quit_event.wait(2), "아이콘이 없어도 설정 화면에서 끝낼 수 있어야 한다"
    finally:
        app.shutdown()


def test_popup_login_flow(home, monkeypatch):
    """로그인 주소를 만들고, Google이 돌려보내는 응답을 받아 토큰을 저장한다."""
    import urllib.parse
    from wurubururu.sources import google_auth
    cc = {"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "s",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}}
    monkeypatch.setattr(google_auth, "bundled_client", lambda: cc)
    assert google_auth.status({})["ready"] is True

    fetched = {}
    from google_auth_oauthlib.flow import Flow
    def fake_fetch(self, **kw):
        fetched.update(kw)
        from google.oauth2.credentials import Credentials
        self.oauth2session.token = {"access_token": "a", "refresh_token": "r"}
    monkeypatch.setattr(Flow, "fetch_token", fake_fetch)
    monkeypatch.setattr(Flow, "credentials", property(lambda self: type("C", (), {"to_json": lambda s: '{"token": "a"}'})()))

    done = []
    login = google_auth.PopupLogin({}, on_done=lambda: done.append(1), timeout=10)
    url = login.start()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert url.startswith("https://accounts.google.com/") and q["access_type"] == ["offline"]
    redirect = q["redirect_uri"][0]
    assert redirect.startswith("http://127.0.0.1:")
    with urllib.request.urlopen(f"{redirect}?state={q['state'][0]}&code=abc&scope=x", timeout=5) as r:
        assert "Google 연결 완료" in r.read().decode()
    for _ in range(50):
        if not login.running:
            break
        time.sleep(0.05)
    assert login.error is None, login.error
    assert done == [1]
    assert fetched["authorization_response"].startswith("https://127.0.0.1:") and "code=abc" in fetched["authorization_response"]
    assert (home / "google_token.json").read_text() == '{"token": "a"}'


def test_popup_login_cancel(home, monkeypatch):
    import urllib.parse
    from wurubururu.sources import google_auth
    cc = {"installed": {"client_id": "c", "client_secret": "s", "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token"}}
    monkeypatch.setattr(google_auth, "bundled_client", lambda: cc)
    login = google_auth.PopupLogin({}, timeout=10)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(login.start()).query)
    with urllib.request.urlopen(f"{q['redirect_uri'][0]}?error=access_denied", timeout=5) as r:
        assert "취소" in r.read().decode()
    for _ in range(50):
        if not login.running:
            break
        time.sleep(0.05)
    assert "취소" in (login.error or "")


def test_https_uses_bundled_certificates():
    from wurubururu import net
    assert net.ca_file() and net.ssl_context().verify_mode.name == "CERT_REQUIRED"
