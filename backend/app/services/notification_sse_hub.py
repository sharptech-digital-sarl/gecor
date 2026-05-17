"""
Hub SSE en mémoire pour notifier les clients connectés (nouvelle notification in-app).

Ne traverse pas les workers Celery ni plusieurs processus uvicorn : dans ces cas,
le polling REST reste le filet de sécurité.
"""

from __future__ import annotations

import json
import queue
import threading
from collections import defaultdict
from typing import Any, DefaultDict
from uuid import UUID


class NotificationSseHub:
    """Un abonné = une queue thread-safe ; publish envoie à tous les onglets de l’utilisateur."""

    def __init__(self) -> None:
        self._by_user: DefaultDict[UUID, list[queue.Queue[str]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, user_id: UUID) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue(maxsize=32)
        with self._lock:
            self._by_user[user_id].append(q)
        return q

    def unsubscribe(self, user_id: UUID, q: queue.Queue[str]) -> None:
        with self._lock:
            subscribers = self._by_user.get(user_id)
            if not subscribers:
                return
            self._by_user[user_id] = [x for x in subscribers if x is not q]
            if not self._by_user[user_id]:
                del self._by_user[user_id]

    def publish(self, user_id: UUID, event: dict[str, Any]) -> None:
        body = json.dumps(event, default=str)
        with self._lock:
            subscribers = list(self._by_user.get(user_id, ()))
        for q in subscribers:
            try:
                q.put_nowait(body)
            except queue.Full:
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(body)
                except queue.Full:
                    pass


notification_sse_hub = NotificationSseHub()
