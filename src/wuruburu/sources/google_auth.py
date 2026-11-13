"""Google 로그인(OAuth). 비밀번호는 저장하지 않고, 읽기 전용 권한 토큰만 ~/.wuruburu 에 둔다."""
from __future__ import annotations

from .. import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
TOKEN_FILE = "google_token.json"


class GoogleSetupError(Exception):
    pass


def credentials(google_cfg: dict, interactive: bool = False):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise GoogleSetupError('Google 연동 패키지가 없습니다: pip install "wuruburu[google]"') from e

    token_path = config.HOME / TOKEN_FILE
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif interactive:
        secret = config.expand(google_cfg.get("client_secret", "~/.wuruburu/client_secret.json"))
        if not secret.exists():
            raise GoogleSetupError(f"OAuth 클라이언트 파일이 없습니다: {secret} (README의 'Google 연결' 참고)")
        creds = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES).run_local_server(port=0)
    else:
        raise GoogleSetupError("Google 로그인이 필요합니다: wuruburu login")
    config.ensure_home()
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:
        pass
    return creds


def service(name: str, version: str, google_cfg: dict):
    from googleapiclient.discovery import build
    return build(name, version, credentials=credentials(google_cfg), cache_discovery=False)
