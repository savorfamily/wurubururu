"""알림 소스. 각 소스는 일정 간격으로 poll(engine)이 불리고, 새 사건이 있으면 engine.post()를 부른다."""
from __future__ import annotations


class Source:
    name = "source"

    def __init__(self, interval: int = 60):
        self.interval = max(5, int(interval))
        self.error: str | None = None

    def poll(self, engine) -> None:
        raise NotImplementedError

    def briefing_lines(self) -> list[str]:
        return []


def build_sources(cfg: dict) -> list[Source]:
    out: list[Source] = []
    if cfg.get("gmail", {}).get("enabled"):
        from .gmail import GmailSource
        out.append(GmailSource(cfg["gmail"], cfg.get("google", {})))
    if cfg.get("calendar", {}).get("enabled"):
        from .gcal import CalendarSource
        out.append(CalendarSource(cfg["calendar"], cfg.get("google", {})))
    sw = cfg.get("sitewatch", {})
    if sw.get("enabled") and sw.get("urls"):
        from .sitewatch import SiteWatchSource
        out.append(SiteWatchSource(sw))
    return out
