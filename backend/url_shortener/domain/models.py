"""Modelos de domínio do encurtador de URLs.

Dataclasses imutáveis (``frozen=True``) que representam as entidades centrais do
domínio. Datas (``created_at``, ``expires_at``, ``timestamp``) são sempre
tratadas em UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UrlMapping:
    """Mapeamento entre um Short_Code e os metadados da URL encurtada."""

    short_code: str
    original_url: str
    created_at: datetime  # UTC
    expires_at: datetime | None


@dataclass(frozen=True)
class ClickRecord:
    """Registro de um acesso (clique) a um Short_Code."""

    short_code: str
    referrer: str | None
    user_agent: str | None
    ip: str | None
    timestamp: datetime  # UTC


@dataclass(frozen=True)
class DayCount:
    """Contagem de cliques agrupada por dia."""

    date: str  # "YYYY-MM-DD"
    count: int


@dataclass(frozen=True)
class ReferrerCount:
    """Contagem de cliques agregada por referrer."""

    referrer: str
    count: int


@dataclass(frozen=True)
class PaginatedResult:
    """Resultado paginado de uma listagem de URLs encurtadas."""

    items: list[dict]
    page: int
    page_size: int
    total: int
    total_pages: int
