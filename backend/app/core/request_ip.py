"""Résolution de l’adresse IP du poste client derrière un reverse proxy (nginx, etc.)."""

from __future__ import annotations

import ipaddress
from typing import Optional

from starlette.requests import Request


def _normalize_ip(candidate: str) -> Optional[str]:
    s = (candidate or "").strip()
    if not s:
        return None
    # "host:port" IPv4 uniquement
    if s.count(":") == 1 and not s.startswith("["):
        host_part = s.rsplit(":", 1)[0]
        try:
            ipaddress.ip_address(host_part)
            return host_part
        except ValueError:
            pass
    try:
        ipaddress.ip_address(s)
        return s
    except ValueError:
        return None


def get_client_ip(request: Request) -> Optional[str]:
    """
    IP vue par l’application : en présence de proxy, lit X-Real-IP puis le 1er hop de X-Forwarded-For,
    sinon l’adresse du socket (request.client).
    Désactiver avec TRUST_FORWARDED_HEADERS=false si l’API est exposée sans proxy (évite le spoofing).
    """
    from app.core.config import settings

    if not settings.TRUST_FORWARDED_HEADERS:
        if request.client and request.client.host:
            return request.client.host
        return None

    real = request.headers.get("x-real-ip")
    if real:
        first = real.split(",")[0].strip()
        parsed = _normalize_ip(first)
        if parsed:
            return parsed

    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        for part in fwd.split(","):
            parsed = _normalize_ip(part)
            if parsed:
                return parsed

    if request.client and request.client.host:
        return request.client.host
    return None
