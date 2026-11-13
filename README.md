# wurubururu

![wurubururu가 하는 일: 메일이 오면 귀가 깜빡이고, 발 버튼으로 열고 듣고, 장애와 작업 완료를 알려줍니다](docs/hero.png)

2001년 딴지일보가 만든 인터넷 라디오 단말 **우르부르(WebToy)** 를 요즘 컴퓨터에서 다시 쓰는 프로그램입니다.
서버는 사라졌지만 기기는 멀쩡합니다. 귀의 LED, 발과 머리의 버튼, 스피커를 직접 제어해서
책상 위 알림 단말로 되살립니다.

- **지원:** macOS (Apple Silicon 포함), Windows 11
- **상태:** 0.1 — 프로토콜은 원본 프로그램 분석으로 복원했고, 아직 실제 기기로는 검증하지 않았습니다.
- 그림은 기능을 설명하는 삽화입니다. 실제 LED 색과 명령어 표기는 아래 본문을 따릅니다.

## 무엇을 해주나

### 알려주기

| 기능 | 동작 |
|---|---|
| **메일** | Gmail에 새 메일이 오면 귀가 깜빡입니다. AI가 "지금 답해야 함 / 보통 / 광고"로 나눠서, 급하면 양쪽 귀가 빠르게, 보통이면 한쪽 귀가 천천히 깜빡이고, 광고는 무시합니다 |
| **일정** | Google 캘린더 일정 10분 전에 한 번, 시작 시각에 한 번 알립니다 |
| **사이트 장애** | 등록한 주소가 연속으로 응답하지 않으면 양쪽 귀 경보와 음성으로 알리고, 복구되면 스스로 꺼집니다 |
| **작업 완료** | `wurubururu notify "빌드 끝"` 한 줄로 빌드·배포·AI 에이전트 작업이 끝났음을 알립니다 |

### 버튼으로 다루기

| 버튼 | 짧게 | 길게 | 두 번 |
|---|---|---|---|
| **왼발** | 방금 알린 메일·링크 열기 | 라디오 켜기/끄기 | 다음 방송 |
| **오른발** | 한 줄 요약 읽어주기 | 집중 타이머 시작/중지 | 브리핑 |
| **머리 (mute)** | 알림 모두 확인 (LED 끔) | 1시간 방해 금지 | 브리핑 |

### 들려주기

| 기능 | 동작 |
|---|---|
| **요약 읽기** | 알림 내용을 한두 문장으로 줄여 스피커로 읽습니다 |
| **아침 브리핑** | 안 읽은 알림과 오늘 일정을 묶어 30초 분량으로 읽습니다 |
| **말투 (보이스 스킨)** | 원본의 보이스 스킨처럼 말투를 고릅니다. 예: `persona = "딴지일보 말투로 능청스럽게"` |
| **라디오** | 인터넷 방송과 팟캐스트 스트림을 틀고 발 버튼으로 채널을 넘깁니다 |
| **인트로** | 켤 때 용팔이(YONGFLY)의 곡 도입부가 한 번 나옵니다 |

### 그 밖에

- **집중 타이머:** 25분 집중하는 동안 한쪽 귀를 켜 두고, 끝나면 알립니다.
- **방해 금지:** 급한 알림만 통과시킵니다.
- **설정 화면:** 브라우저로 여는 로컬 페이지에서 상태 확인, LED 시험, 설정 편집을 합니다.
- **AI 선택:** Gemini, Claude, Grok 중에서 고릅니다. AI 없이도 동작합니다.

## 설치

### macOS

```
brew install libusb
pip install "wurubururu[all] @ git+https://github.com/savorfamily/wurubururu"
```

- 드라이버 설치가 필요 없습니다. 스피커는 꽂으면 바로 소리 출력 장치로 잡힙니다.
- 읽어주기는 macOS 내장 음성을 씁니다. `voice = "Yuna"`처럼 목소리를 고를 수 있습니다.
- `audio_device`에 우르부르 스피커 이름을 적으면 다른 소리는 그대로 두고 알림 음성만 우르부르로 보냅니다.
- 라디오를 쓰려면 `brew install mpv`.

### Windows 11

```
pip install "wurubururu[all] @ git+https://github.com/savorfamily/wurubururu"
```

1. [Zadig](https://zadig.akeo.ie)를 실행하고 Options → List All Devices를 켭니다.
2. 우르부르의 **인터페이스 2 (HID, MI_02)** 를 골라 WinUSB를 설치합니다.
3. 오디오 인터페이스는 건드리지 않습니다. 스피커 기능은 그대로 유지됩니다.

- 2001년 원본 드라이버는 필요 없고, 설치되지도 않습니다.
- 읽어주기는 Windows 내장 음성을 쓰며, 기본 소리 출력 장치로 나옵니다. 우르부르로 듣고 싶으면 기본 출력 장치를 우르부르로 바꿉니다.
- 라디오를 쓰려면 mpv, ffplay, VLC 중 하나를 설치합니다.
- Python 3.11 이상이 필요합니다.

### OS별 차이

| | macOS | Windows 11 |
|---|---|---|
| 드라이버 | 필요 없음 | Zadig로 WinUSB 한 번 설치 |
| 추가 설치 | libusb | 없음 |
| 음성 | 내장 음성, 목소리 선택 가능 | 내장 음성 |
| 알림 음성만 우르부르로 | 가능 (`audio_device`) | 기본 출력 장치를 따름 |
| 트레이 아이콘 | 메뉴 막대 | 작업 표시줄 알림 영역 |

## 처음 한 번: 기기 확인

```
wurubururu info       # 기기가 잡히는지
wurubururu leds       # 비트별로 어느 귀가 무슨 색인지
wurubururu buttons    # 어느 버튼이 어느 비트인지
```

버튼 비트가 기본값과 다르면 설정 파일의 `[device.buttons]`를 고칩니다.
기기 없이 둘러보려면 `wurubururu --mock run`.

## 실행

```
wurubururu config     # 설정 파일을 만들고 위치를 알려줌
wurubururu login      # Google 계정 연결
wurubururu run        # 상주 실행. 설정 화면: http://127.0.0.1:8737/
```

자주 쓰는 명령:

```
wurubururu blink urgent          # LED 패턴 재생 (left, right, both, urgent, alarm, pulse ...)
wurubururu notify "배포 끝" --urgent
wurubururu say "점심 먹을 시간"
wurubururu ai "안녕"              # AI 연결 시험
```

## AI 고르기

설정 파일 `[ai]`의 `provider`에 하나를 적습니다.

| provider | 필요한 것 | 비고 |
|---|---|---|
| `gemini` | Gemini API 키 (`GEMINI_API_KEY`) | 기본값 |
| `claude` | Claude API 키 (`ANTHROPIC_API_KEY`) | Claude Console에서 발급. Pro 구독과 별도 과금 |
| `grok` | xAI API 키 (`XAI_API_KEY`) | |
| `claude_cli` | 설치·로그인된 Claude Code | Claude 구독(Pro 등) 사용량으로 동작 |
| `none` | 없음 | 분류·요약 없이 모든 메일을 보통 알림으로 처리 |

모델 이름은 각 `[ai.<이름>]` 절의 `model`에서 바꿉니다.

**개인정보:** 기본값 `privacy = "headers"`에서는 보낸 사람과 제목만 AI로 보냅니다.
`"snippet"`으로 바꾸면 본문 미리보기도 보내서 요약이 좋아집니다.

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
