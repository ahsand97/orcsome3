from __future__ import annotations

import subprocess
from typing import List, Optional

_default_appname = "orcsome3"


def notify(summary: str, body: str, timeout: int = -1, urgency: int = 1, appname: Optional[str] = None) -> Notification:
    n: Notification = Notification(
        summary=summary, body=body, timeout=timeout, urgency=urgency, appname=appname or _default_appname
    )
    n.show()
    return n


class Notification(object):
    def __init__(self, summary: str, body: str, timeout: int, urgency: int, appname: str) -> None:
        self.summary: str = summary.lstrip("-")
        self.body: str = body
        self.timeout: int = timeout
        self.urgency: int = urgency
        self.appname: str = appname
        self.replace_id: int = 0
        self.lastcmd: List[str] = []

    def show(self) -> None:
        timeout: int = self.timeout * 1000
        if timeout < 0:
            timeout = -1

        urgency: str = "{}"
        if self.urgency != 1:
            urgency = f"{'urgency': <byte {self.urgency}>}"

        cmd: List[str] = [
            "gdbus",
            "call",
            "--session",
            "--dest=org.freedesktop.Notifications",
            "--object-path=/org/freedesktop/Notifications",
            "--method=org.freedesktop.Notifications.Notify",
            self.appname,
            str(self.replace_id),
            "",
            self.summary,
            self.body,
            "[]",
            urgency,
            str(timeout),
        ]
        self.lastcmd = cmd

        out, error = subprocess.Popen(args=cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()

        if error:
            raise Exception(error)

        self.replace_id = int(out.strip().split()[1].rstrip(b",)"))

    def update(
        self,
        summary: Optional[str] = None,
        body: Optional[str] = None,
        timeout: Optional[int] = None,
        urgency: Optional[int] = None,
    ) -> None:
        if summary is not None:
            self.summary = summary

        if body is not None:
            self.body = body

        if timeout is not None:
            self.timeout = timeout

        if urgency is not None:
            self.urgency = urgency

        self.show()

    def close(self) -> None:
        cmd: List[str] = [
            "gdbus",
            "call",
            "--session",
            "--dest=org.freedesktop.Notifications",
            "--object-path=/org/freedesktop/Notifications",
            "--method=org.freedesktop.Notifications.CloseNotification",
            str(self.replace_id),
        ]

        _, error = subprocess.Popen(args=cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()
        if error:
            raise Exception(error)
