## 0.3.0에서 달라진 점

- **Google 로그인 한 번으로 Gmail·캘린더 연결.** 클라이언트 파일을 따로 만들 필요가 없습니다. 설정 화면 → Gmail·캘린더 → **Google로 로그인 → 허용**.
- Gmail 권한을 머리글 전용(`gmail.metadata`)으로 줄였습니다. 메일 본문은 읽지 않습니다.
- Gmail·캘린더 정보는 AI로 보내지 않고, 기록 파일에도 남기지 않습니다. [개인정보처리방침](https://savorfamily.github.io/privacy.html)
- 중요·별표 메일은 빨강, 그 밖의 메일은 초록. 프로모션·소셜·포럼 메일은 알리지 않습니다.
- 이전 버전에서 연결해 둔 Google 계정은 한 번 다시 로그인해야 합니다.

Google 앱 심사가 끝나기 전에는 로그인할 때 "Google에서 확인하지 않은 앱" 화면이 나올 수 있습니다. **고급 → wurubururu(으)로 이동**을 누르세요.

## 내려받기

| 컴퓨터 | 파일 |
|---|---|
| 맥 (M1·M2·M3·M4 등 Apple Silicon) | `wurubururu-…-mac-apple-silicon.dmg` |
| 맥 (Intel) | `wurubururu-…-mac-intel.dmg` |
| Windows 11 | `wurubururu-…-windows-setup.exe` |

## 맥에서 처음 열 때

터미널에 아래 한 줄을 붙여넣으면 설치·업데이트가 한 번에 끝나고 보안 경고도 뜨지 않습니다.

```
curl -fsSL https://raw.githubusercontent.com/savorfamily/wurubururu/main/install.sh | bash
```

직접 설치할 때는:

1. dmg를 열고 `wurubururu`를 응용 프로그램 폴더로 끌어다 놓습니다.
2. 응용 프로그램 폴더에서 `wurubururu`를 **우클릭 → 열기**를 누르고, 경고 창에서 다시 **열기**를 누릅니다.
   서명하지 않은 앱이라 처음 한 번만 이렇게 열어야 합니다.
   "열기" 버튼이 없으면 시스템 설정 → 개인정보 보호 및 보안 맨 아래의 **그래도 열기**를 누릅니다.
3. 메뉴 막대에 우르부르르 아이콘이 생기고 설정 화면이 브라우저로 열립니다.

## Windows에서 처음 열 때

1. 설치 파일을 실행합니다. "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**을 누릅니다.
2. 처음 한 번 [Zadig](https://zadig.akeo.ie)로 우르부르의 **인터페이스 2 (MI_02)** 에 WinUSB 드라이버를 설치합니다.
   자세한 방법은 [README](https://github.com/savorfamily/wurubururu#windows-11)를 참고하세요.

인트로 음원(용팔이 「긍정주의자」)은 MIT 적용 제외, 모든 권리 보유입니다.
