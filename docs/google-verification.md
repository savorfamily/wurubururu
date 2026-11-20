# Google OAuth 앱 심사 자료

Google Cloud 콘솔 → Google 인증 플랫폼 → **인증 센터**에서 심사를 신청할 때 붙여넣을 내용입니다.
심사는 영어로 진행되므로 붙여넣는 글은 영어로 둡니다. 한국어는 이해를 돕는 설명입니다.

## 기본 정보

| 항목 | 값 |
|---|---|
| 앱 이름 | wurubururu |
| 홈페이지 | https://savorfamily.github.io/ |
| 개인정보처리방침 | https://savorfamily.github.io/privacy.html |
| 서비스 약관 | https://savorfamily.github.io/terms.html |
| 승인된 도메인 | savorfamily.github.io (Search Console 소유권 확인 완료) |
| 클라이언트 유형 | 데스크톱 앱 (설치형, 루프백 리디렉션) |
| 범위 | `gmail.metadata` (제한), `calendar.events.readonly` (민감) |

## 앱 설명 (App description)

> wurubururu is a free, open-source desktop app for macOS and Windows that turns the "Wuruburu" USB toy (released in Korea in 2001) into a desk notification device. When a new unread email arrives in the user's Gmail inbox, or a Google Calendar event is about to start, the toy's ear LEDs blink. Pressing the toy's foot button opens the message or event in the user's browser, or reads its sender and subject aloud with the computer's built-in text-to-speech.
>
> The app runs entirely on the user's own computer and connects directly to Google APIs. There is no developer-operated server: Google user data is never transmitted to, stored on, or accessible by the developer, and it is never sent to any AI service. Source code: https://github.com/savorfamily/wurubururu

## 범위별 사용 이유 (Scope justification)

### `https://www.googleapis.com/auth/gmail.metadata`

> wurubururu needs to know when a new unread email arrives in the user's Inbox and who it is from, so it can blink the toy's ear lights and, when the user presses the toy's button, read the sender and subject aloud or open that message in Gmail.
>
> The app calls users.messages.list with labelIds INBOX and UNREAD (optionally IMPORTANT), then users.messages.get with format=metadata and metadataHeaders From and Subject. It uses the message's labels (IMPORTANT, STARRED, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, CATEGORY_FORUMS) to decide the LED color and to skip promotional mail.
>
> We deliberately chose gmail.metadata, the narrowest Gmail scope that provides labels and headers, instead of gmail.readonly, because the app never needs message bodies or attachments. Narrower scopes are not sufficient: gmail.labels does not return messages, and the non-restricted scopes (gmail.send, gmail.compose, etc.) do not allow reading new-message metadata. The app never sends, modifies, or deletes mail.
>
> All processing happens locally on the user's device. The data is held in memory only while the notification is shown, is not written to disk or logs, is never transmitted to the developer or any third party, and is never sent to any AI service or used to train models.

### `https://www.googleapis.com/auth/calendar.events.readonly`

> wurubururu reminds the user of upcoming meetings by blinking the toy's right ear 10 minutes before an event on the user's primary calendar starts, and again at the start time. When the user presses the button, it reads the event title aloud or opens the event in Google Calendar.
>
> The app calls events.list on the primary calendar for the next 18 hours and uses only the event ID, title (summary), start time, and htmlLink. It is read-only and never creates, changes, or deletes events. calendar.events.readonly is the narrowest scope that returns event times and titles; calendar.calendarlist.readonly and calendar.settings.readonly do not include events.
>
> Data is processed only on the user's device, is not stored or logged, and is never shared with the developer, third parties, or AI services.

## 보안 평가(CASA) 관련 답변

`gmail.metadata`는 제한된 범위라 보안 평가 대상인지 묻습니다. 평가는 제한된 범위 데이터가 개발자 서버로 전송되거나 저장되는 경우에만 필요합니다. 우르부르르는 해당하지 않으므로 아래처럼 답합니다.

> wurubururu is an installed desktop application. Restricted-scope data is accessed directly from the user's device to Google APIs and is processed only in memory on that device. It is never transmitted to, stored on, or accessible from any server operated by the developer or any third party. The only persisted item is the OAuth token, stored in the user's home folder (~/.wurubururu/google_token.json) with permissions restricted to the user. Therefore, we believe a third-party security assessment is not required.

## 시연 영상 (YouTube, 일부 공개)

Google이 요구하는 것: 실제 앱에서 **동의 화면 전체(앱 이름·범위 보이게)**, 그리고 **각 범위의 데이터를 쓰는 기능**이 화면에 나와야 합니다. 영상은 영어 자막이나 영어 설명을 넣습니다. 길이는 2~3분이면 충분합니다.

| 순서 | 화면 | 자막·설명 (영어) |
|---|---|---|
| 1 | 우르부르 기기를 컴퓨터에 꽂고 우르부르르 실행. 메뉴 막대 아이콘 | "wurubururu is a desktop app that turns the Wuruburu USB toy into a desk notifier." |
| 2 | 설정 화면 → Gmail·캘린더 → **Google로 로그인** 클릭 | "The user signs in with Google from the app's local settings page." |
| 3 | Google 계정 선택 화면. **주소창의 client_id가 보이도록** 잠깐 확대 | "OAuth client used by the app." |
| 4 | 동의 화면. 앱 이름 **wurubururu**와 두 권한(메일 메타데이터, 캘린더 일정 보기)이 보이게 천천히 스크롤 → **허용** | "The app requests only read-only Gmail metadata and Calendar events." |
| 5 | 설정 화면에 "연결됨" 표시 | |
| 6 | 다른 계정이나 휴대폰에서 시험 메일을 보냄 → 기기 왼쪽 귀가 초록으로 깜빡임 (기기를 화면에 잡기) | "gmail.metadata: a new unread email makes the left ear blink." |
| 7 | 별표 또는 중요 메일 → 빨강 | "Gmail's Important / Starred labels decide the color." |
| 8 | 오른발 버튼 → 보낸 사람·제목을 소리로 읽음 | "The sender and subject are read aloud locally. The message body is never accessed." |
| 9 | 왼발 버튼 → 브라우저에서 해당 메일이 Gmail로 열림 | "The left foot opens the message in Gmail." |
| 10 | 몇 분 뒤 시작하는 캘린더 일정 → 오른쪽 귀 초록. 버튼 → 일정 열림 | "calendar.events.readonly: upcoming events trigger the right ear." |
| 11 | 설정 화면 → **연결 해제** → myaccount.google.com/permissions 에서 앱이 사라진 것 확인 | "Users can disconnect at any time; the token is deleted locally." |
| 12 | 개인정보처리방침 페이지를 잠깐 보여줌 | "Google data never leaves the user's computer and is never sent to AI." |

녹화 팁: 맥은 Shift+Command+5, 윈도우는 Win+Alt+R(Xbox Game Bar). 기기 불빛은 휴대폰으로 찍어 화면 녹화와 나란히 붙여도 됩니다. YouTube에 **일부 공개(Unlisted)** 로 올리고 링크를 신청서에 넣습니다.

## 제출 순서

1. Google 인증 플랫폼 → **대상** → 게시 상태 **앱 게시** (테스트 → 프로덕션). 이때부터 누구나 로그인할 수 있지만, 심사 전에는 "확인되지 않은 앱" 경고가 뜨고 최대 100명까지만 쓸 수 있습니다.
2. **인증 센터** → 심사 준비 항목 확인 → 위의 범위별 이유, 시연 영상 링크 입력 → 제출.
3. Google 심사팀이 Search Console 계정 메일(지원 이메일)로 질문을 보낼 수 있습니다. 답장은 영어로 짧게, 이 문서의 내용을 근거로.
4. 민감·제한 범위 심사는 보통 수 주가 걸립니다.
