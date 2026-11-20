"""Gmail 새 메일 감지.

gmail.metadata 범위만 쓴다: 메일 머리글(보낸 사람·제목)과 라벨만 읽고, 본문·첨부는 읽지 않는다.
이 범위에서는 Gmail 검색어를 쓸 수 없으므로 라벨(받은편지함·읽지 않음·중요)로 거른다.
급한 메일 구분도 AI 없이 Gmail이 매긴 라벨로 이 컴퓨터 안에서 한다 (메일 정보는 AI로 보내지 않음).
"""
from __future__ import annotations

from . import Source
from ..engine import Alert

QUIET_CATEGORIES = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"}


def priority_from_labels(labels: list[str], cfg: dict) -> str:
    """Gmail 라벨로 중요도를 정한다: 중요 표시 → 급함, 프로모션·소셜·포럼 탭 → 알리지 않음, 나머지 → 보통."""
    labels = set(labels or [])
    if cfg.get("ignore_promotions", True) and labels & QUIET_CATEGORIES:
        return "ignore"
    if cfg.get("important_is_urgent", True) and ("IMPORTANT" in labels or "STARRED" in labels):
        return "urgent"
    return "normal"


class GmailSource(Source):
    name = "gmail"

    def __init__(self, cfg: dict, google_cfg: dict, service=None):
        super().__init__(cfg.get("interval", 60))
        self.cfg = cfg
        self.labels = ["INBOX", "UNREAD"] + (["IMPORTANT"] if cfg.get("important_only") else [])
        self.google_cfg = google_cfg
        self._service = service
        self._seen: set[str] | None = None   # 처음 한 번은 기존 메일을 알리지 않고 기억만 한다

    def _svc(self):
        if self._service is None:
            from .google_auth import service
            self._service = service("gmail", "v1", self.google_cfg)
        return self._service

    def poll(self, engine) -> None:
        svc = self._svc()
        res = svc.users().messages().list(userId="me", labelIds=self.labels, maxResults=25).execute()
        ids = [m["id"] for m in res.get("messages", [])]
        if self._seen is None:
            self._seen = set(ids)
            return
        for mid in reversed([i for i in ids if i not in self._seen]):
            self._seen.add(mid)
            msg = svc.users().messages().get(
                userId="me", id=mid, format="metadata", metadataHeaders=["From", "Subject"]).execute()
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            sender = headers.get("from", "")
            subject = headers.get("subject", "(제목 없음)")
            engine.post(Alert(
                kind="mail", title=f"{sender.split('<')[0].strip() or sender}: {subject}",
                priority=priority_from_labels(msg.get("labelIds", []), self.cfg),
                url=f"https://mail.google.com/mail/u/0/#inbox/{msg.get('threadId', mid)}", key=mid))
        if len(self._seen) > 2000:
            self._seen = set(ids)
