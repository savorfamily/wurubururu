# wurubururu

2001년 딴지일보가 만든 인터넷 라디오 단말 **우르부르(WebToy)** 를 요즘 컴퓨터에서 다시 쓰기 위한 프로그램입니다.
원래 서버는 사라졌지만 기기 자체는 멀쩡합니다. 이 프로그램은 귀의 LED, 발과 머리의 버튼, 스피커를 직접 제어해서
메일·일정·사이트 장애 알림 단말로 되살립니다.

- 지원: macOS (Apple Silicon 포함), Windows 11
- 상태: **0.1 — 실제 기기 검증 전.** 프로토콜은 원본 프로그램 분석으로 복원했고, 가짜 장치(mock)로만 시험했습니다.

## 할 수 있는 일

| 기능 | 설명 |
|---|---|
| Gmail 알림 | 새 메일이 오면 귀가 깜빡입니다. AI가 급한 메일·보통 메일·광고를 구분합니다 |
| 일정 알림 | Google 캘린더 일정 10분 전과 시작 시각에 알립니다 |
| 사이트 감시 | 등록한 주소가 연속으로 응답하지 않으면 경보, 복구되면 자동 해제 |
| 읽어주기 | 알림 요약과 아침 브리핑을 스피커로 읽어줍니다 (말투 지정 가능) |
| 라디오 | 인터넷 방송을 틀고 버튼으로 채널을 넘깁니다 |
| 집중 타이머 | 25분 집중 / 5분 휴식 |
| 외부 알림 | `wurubururu notify "빌드 끝"` 한 줄로 다른 프로그램이 귀를 깜빡이게 합니다 |
| 방해 금지 | 급한 알림만 통과 |
| 인트로 | 프로그램을 켤 때 인트로 음원을 한 번 재생합니다 |

### 버튼 기본 배치

| 버튼 | 짧게 | 길게 | 두 번 |
|---|---|---|---|
| 왼발 | 최근 알림 열기 | 라디오 켜기/끄기 | 다음 방송 |
| 오른발 | 요약 읽어주기 | 집중 타이머 | 브리핑 |
| 머리(mute) | 모두 확인(LED 끔) | 방해 금지 | 브리핑 |

배치와 LED 패턴은 설정 파일에서 바꿀 수 있습니다.

## 설치

```
pip install "wurubururu[all] @ git+https://github.com/<계정>/wurubururu"
```

- **macOS:** `brew install libusb`
- **Windows 11:** [Zadig](https://zadig.akeo.ie)를 실행해 우르부르의 **인터페이스 2 (HID, MI_02)** 에만 WinUSB를 설치합니다.
  오디오 인터페이스는 건드리지 마세요. 스피커 기능은 그대로 유지됩니다.

## 처음 한 번: 기기 확인

```
wurubururu info       # 기기가 잡히는지
wurubururu leds       # 비트별로 어느 귀가 무슨 색인지
wurubururu buttons    # 어느 버튼이 어느 비트인지
```

버튼 비트가 기본값과 다르면 설정 파일의 `[device.buttons]`를 고칩니다. 기기 없이 둘러보려면 `wurubururu --mock run`.

## 실행

```
wurubururu config     # 설정 파일 만들고 위치 출력
wurubururu login      # Google 계정 연결 (아래 'Google 연결' 참고)
wurubururu run        # 상주 실행. 설정 화면: http://127.0.0.1:8737/
```

## AI 고르기

설정 파일 `[ai]`의 `provider`에 하나를 적습니다.

| provider | 필요한 것 | 비고 |
|---|---|---|
| `gemini` | Gemini API 키 (`GEMINI_API_KEY`) | 기본값 |
| `claude` | Claude API 키 (`ANTHROPIC_API_KEY`) | Claude Console에서 발급. **Pro 구독과 별도 과금** |
| `grok` | xAI API 키 (`XAI_API_KEY`) | |
| `claude_cli` | 설치·로그인된 Claude Code | Claude 구독(Pro 등) 사용량으로 동작 |
| `none` | 없음 | 분류·요약 없이 모든 메일을 보통 알림으로 처리 |

모델 이름은 각 `[ai.<이름>]` 절의 `model`에서 바꿉니다. 연결 시험: `wurubururu ai "안녕"`.

**개인정보:** 기본값 `privacy = "headers"`에서는 보낸 사람과 제목만 AI로 전송합니다.
`"snippet"`으로 바꾸면 본문 미리보기도 전송되어 요약이 좋아집니다.

## Google 연결

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 만들고 Gmail API와 Calendar API를 켭니다.
2. OAuth 클라이언트(데스크톱 앱)를 만들어 JSON을 내려받아 `~/.wurubururu/client_secret.json`에 둡니다.
3. `wurubururu login`을 실행하면 브라우저가 열립니다. 읽기 전용 권한만 요청합니다.

## 인트로 음원

프로그램을 켤 때 용팔이(YONGFLY)의 앨범 「긍정주의자 (Positiveist)」 수록곡 도입부를 한 번 재생합니다.
끄려면 설정 파일 `[intro]`의 `enabled = false`, 다른 음원을 쓰려면 `file`에 경로를 적습니다.

이 음원은 MIT 적용 대상이 아니며 모든 권리가 보유됩니다. 자세한 내용은
[src/wurubururu/assets/LICENSE-AUDIO.md](src/wurubururu/assets/LICENSE-AUDIO.md).

## 구조

```
sources/ (gmail, gcal, sitewatch, 외부 notify)
      ↓ Alert
engine.py  ←→  ai.py (gemini / claude / grok / claude_cli)
      ↓
leds.py · actions.py(말하기, 열기, 라디오)  ←  buttons.py
      ↓                                          ↑
device.py (USB 벤더 컨트롤 전송) ─────────────────┘
```

프로토콜 상세는 [docs/PROTOCOL.md](docs/PROTOCOL.md).

## 개발

```
pip install -e ".[dev]"
pytest
```

## 알아둘 점

- 원본 설치 프로그램과 드라이버는 딴지그룹과 Micronas의 저작물이라 이 저장소에 포함하지 않습니다.
- 이 프로젝트는 딴지그룹과 관계없는 비공식 프로젝트입니다.

## 만든 사람

용팔이 (YONGFLY)

## 라이선스

코드는 MIT.

인트로 음원(`src/wurubururu/assets/intro.mp3`)은 MIT 적용 제외이며 모든 권리 보유(All rights reserved)입니다.
