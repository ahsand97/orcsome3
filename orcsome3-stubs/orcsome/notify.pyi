from typing import List, Optional


def notify(summary: str, body: str, timeout: int = ..., urgency: int = ..., appname: Optional[str] = ...) -> Notification: ...

class Notification:
    summary: str
    body: str
    timeout: int
    urgency: int
    appname: str
    replace_id: int
    lastcmd: List[str]
    def __init__(self, summary: str, body: str, timeout: int, urgency: int, appname: str) -> None: ...
    def show(self) -> None: ...
    def update(self, summary: Optional[str] = ..., body: Optional[str] = ..., timeout: Optional[int] = ..., urgency: Optional[int] = ...) -> None: ...
    def close(self) -> None: ...
