"""운영 중인 사이트 감시. 연속으로 응답이 없으면 알리고, 복구되면 알림을 내린다."""
from __future__ import annotations

import urllib.error
import urllib.request

from . import Source
from ..engine import Alert


def check(url: str, timeout: int = 10) -> str | None:
    """정상이면 None, 문제가 있으면 이유를 돌려준다."""
    req = urllib.request.Request(url, headers={"User-Agent": "wurubururu-sitewatch"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return None if r.status < 500 else f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return None if e.code < 500 else f"HTTP {e.code}"
    except Exception as e:
        return str(getattr(e, "reason", e))[:120]


class SiteWatchSource(Source):
    name = "sitewatch"

    def __init__(self, cfg: dict, checker=check):
        super().__init__(cfg.get("interval", 120))
        self.urls = [u for u in cfg.get("urls", []) if str(u).startswith(("http://", "https://"))]
        self.threshold = max(1, int(cfg.get("fail_threshold", 2)))
        self.checker = checker
        self.fails: dict[str, int] = {}

    def poll(self, engine) -> None:
        for url in self.urls:
            problem = self.checker(url)
            if problem is None:
                if self.fails.pop(url, 0) >= self.threshold:
                    engine.note(f"사이트 복구: {url}")
                    engine.resolve("site", url)
                continue
            self.fails[url] = self.fails.get(url, 0) + 1
            if self.fails[url] == self.threshold:
                engine.post(Alert("site", f"사이트 응답 없음: {url}", body=problem,
                                  priority="urgent", url=url, key=url))
                engine.say("사이트가 응답하지 않습니다")
