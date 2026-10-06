"""Serviço de listagem de URLs encurtadas (``GET /api/urls``).

Orquestra a recuperação dos mapeamentos no :class:`UrlRepository`, a ordenação
exigida pelo negócio (decrescente por ``createdAt`` e, em empate, decrescente
por ``shortCode`` — Req 3.2), a paginação (via :func:`paginate` — Req 3.5, 3.6)
e o enriquecimento de cada item com ``clickCount`` consultado no
:class:`AnalyticsRepository` (Req 3.1).

A indisponibilidade da origem de dados é propagada como
:class:`DataSourceError` (Req 3.12), traduzida para HTTP 503 pela camada de
rotas.
"""

from __future__ import annotations

from datetime import datetime, timezone

from url_shortener.domain.errors import DataSourceError
from url_shortener.domain.models import PaginatedResult, UrlMapping
from url_shortener.pagination import paginate
from url_shortener.repositories.analytics_repository import AnalyticsRepository
from url_shortener.repositories.url_repository import UrlRepository


def _to_iso_utc(value: datetime) -> str:
    """Serializa um ``datetime`` em ISO 8601 UTC com sufixo ``Z``.

    Datas ingênuas (sem fuso) são assumidas como UTC; datas com fuso são
    convertidas para UTC. O resultado usa o sufixo ``Z`` conforme o contrato
    da API (ex.: ``2025-01-10T12:00:00Z``).
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class ListService:
    """Monta a listagem paginada de URLs encurtadas com contagem de cliques."""

    def __init__(
        self,
        base_url: str,
        url_repository: UrlRepository,
        analytics_repository: AnalyticsRepository,
    ) -> None:
        """Inicializa o serviço.

        Args:
            base_url: domínio base usado para montar a ``shortUrl`` de cada
                item (ex.: ``https://host``).
            url_repository: repositório de URLs (Redis) para recuperar os
                mapeamentos.
            analytics_repository: repositório de analytics (SQLite) para a
                contagem de cliques por code.
        """
        self._base_url = base_url.rstrip("/")
        self._url_repository = url_repository
        self._analytics_repository = analytics_repository

    def list_urls(self, page: int, page_size: int) -> PaginatedResult:
        """Lista as URLs encurtadas de forma ordenada e paginada.

        Recupera todos os mapeamentos, ordena de forma decrescente por
        ``createdAt`` e, em empate, decrescente por ``shortCode`` (Req 3.2);
        aplica a paginação sobre a lista ordenada (Req 3.5, 3.6); e enriquece
        cada item da página com ``clickCount`` via ``count_clicks_bulk``
        (Req 3.1). Quando não há URLs ou a página excede o total, os itens
        resultam em uma lista vazia (Req 3.11, 3.10).

        Args:
            page: página solicitada (iniciando em 1); assume-se já validada.
            page_size: tamanho da página (>= 1); assume-se já validado/limitado.

        Returns:
            Um :class:`PaginatedResult` com os itens da página (cada um com
            ``shortCode``, ``shortUrl``, ``originalUrl``, ``createdAt``,
            ``expiresAt`` e ``clickCount``) e os metadados de paginação.

        Raises:
            DataSourceError: se a origem de dados estiver indisponível durante
                a recuperação dos mapeamentos ou da contagem de cliques
                (Req 3.12).
        """
        mappings = self._url_repository.list_mappings()

        ordered = sorted(
            mappings,
            key=lambda m: (m.created_at, m.short_code),
            reverse=True,
        )

        result = paginate([None] * len(ordered), page, page_size)

        offset = (page - 1) * page_size
        page_mappings = ordered[offset : offset + page_size]

        click_counts = self._count_clicks(
            [mapping.short_code for mapping in page_mappings]
        )

        items = [
            self._build_item(mapping, click_counts.get(mapping.short_code, 0))
            for mapping in page_mappings
        ]

        return PaginatedResult(
            items=items,
            page=result.page,
            page_size=result.page_size,
            total=result.total,
            total_pages=result.total_pages,
        )

    def _count_clicks(self, codes: list[str]) -> dict[str, int]:
        """Consulta a contagem de cliques por code, tratando indisponibilidade.

        Converte qualquer falha de leitura do Analytics_Store em
        :class:`DataSourceError` (Req 3.12), para que a listagem não retorne
        um resultado parcial.
        """
        try:
            return self._analytics_repository.count_clicks_bulk(codes)
        except DataSourceError:
            raise
        except Exception as exc:  # noqa: BLE001 - encapsula indisponibilidade de I/O
            raise DataSourceError(
                "Falha temporária ao recuperar as métricas de cliques."
            ) from exc

    def _build_item(self, mapping: UrlMapping, click_count: int) -> dict:
        """Monta o item da listagem com todos os campos exigidos (Req 3.1)."""
        return {
            "shortCode": mapping.short_code,
            "shortUrl": f"{self._base_url}/{mapping.short_code}",
            "originalUrl": mapping.original_url,
            "createdAt": _to_iso_utc(mapping.created_at),
            "expiresAt": (
                _to_iso_utc(mapping.expires_at)
                if mapping.expires_at is not None
                else None
            ),
            "clickCount": click_count,
        }
