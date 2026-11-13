"""Google 캘린더 일정 임박 알림. 시작 N분 전에 한 번, 시작 시각에 한 번 알린다."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import Source
from ..engine import Alert


class CalendarSource(Source):
    name = "calendar"

    def __init__(self, cfg: dict, google_cfg: dict, service=None):
        super().__init__(cfg.get("interval", 120))
        self.lead = int(cfg.get("lead_minutes", 10))
        self.google_cfg = google_cfg
        self._service = service
        self._today: list[str] = []

    def _svc(self):
        if self._service is None:
            from .google_auth import service
            self._service = service("calendar", "v3", self.google_cfg)
        return self._service

    def poll(self, engine, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        end = now + timedelta(hours=18)
        res = self._svc().events().list(
            calendarId="primary", timeMin=now.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=20).execute()
        today = []
        for ev in res.get("items", []):
            start_raw = ev.get("start", {}).get("dateTime")
            if not start_raw:      # 종일 일정은 건너뜀
                continue
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            title = ev.get("summary", "(제목 없는 일정)")
            today.append(f"{start.astimezone().strftime('%H:%M')} {title}")
            minutes = (start - now).total_seconds() / 60
            url = ev.get("htmlLink", "")
            if minutes <= 1:
                engine.resolve("calendar", f"{ev['id']}-lead")
                engine.post(Alert("calendar", f"지금 시작: {title}", priority="urgent",
                                  url=url, key=f"{ev['id']}-start"))
            elif minutes <= self.lead:
                engine.post(Alert("calendar", f"{int(minutes)}분 뒤: {title}",
                                  url=url, key=f"{ev['id']}-lead"))
        self._today = today

    def briefing_lines(self) -> list[str]:
        return [f"[일정] {t}" for t in self._today[:8]]
