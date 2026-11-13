"""Gmail 새 메일 감지."""
from __future__ import annotations

from . import Source
from ..engine import Alert


class GmailSource(Source):
    name = "gmail"

    def __init__(self, cfg: dict, google_cfg: dict, service=None):
        super().__init__(cfg.get("interval", 60))
        self.query = cfg.get("query", "is:unread in:inbox newer_than:1d")
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
        res = svc.users().messages().list(userId="me", q=self.query, maxResults=25).execute()
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
            verdict = engine.triage_mail(sender, subject, msg.get("snippet", ""))
            engine.post(Alert(
                kind="mail", title=f"{sender.split('<')[0].strip() or sender}: {subject}",
                body=msg.get("snippet", ""), priority=verdict["priority"], summary=verdict["summary"],
                url=f"https://mail.google.com/mail/u/0/#inbox/{msg.get('threadId', mid)}", key=mid))
        if len(self._seen) > 2000:
            self._seen = set(ids)
