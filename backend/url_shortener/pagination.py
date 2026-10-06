"""Cálculo de paginação: offset, total e totalPages.

Utilitário puro que aplica a paginação sobre uma lista já ordenada de itens,
montando um :class:`PaginatedResult` com os metadados exigidos pela listagem de
URLs encurtadas (``GET /api/urls``).

Regras (Requisitos 3.5, 3.6, 3.10):
- O deslocamento é calculado como ``offset = (page - 1) * page_size``.
- Os itens retornados são o recorte ``items[offset : offset + page_size]`` da
  lista ordenada; quando a página solicitada excede o total, o recorte resulta
  em uma lista vazia.
- ``total`` reflete o número real de itens existentes.
- ``total_pages`` é ``ceil(total / page_size)``.
"""

from __future__ import annotations

from math import ceil

from url_shortener.domain.models import PaginatedResult


def paginate(items: list[dict], page: int, page_size: int) -> PaginatedResult:
    """Aplica a paginação sobre ``items`` (lista já ordenada).

    Args:
        items: lista completa de itens já ordenada conforme a regra de negócio.
        page: página solicitada (iniciando em 1); assume-se já validada.
        page_size: tamanho da página (>= 1); assume-se já validado/limitado.

    Returns:
        Um :class:`PaginatedResult` com o recorte da página e os metadados
        ``page``, ``page_size``, ``total`` e ``total_pages``.
    """
    total = len(items)
    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size]
    total_pages = ceil(total / page_size) if page_size > 0 else 0

    return PaginatedResult(
        items=page_items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )
