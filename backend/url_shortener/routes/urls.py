"""Rota de listagem paginada de URLs encurtadas (``GET /api/urls``).

Esta camada traduz a requisição HTTP em uma chamada ao :class:`ListService`
(obtido do contexto da aplicação Flask), sem conter regra de negócio:

- Lê ``page`` e ``pageSize`` da query string e os valida/normaliza via
  :func:`parse_pagination` (defaults ``page=1``/``pageSize=50`` e limite de 100
  — Req 3.3, 3.4, 3.7).
- Delega a ordenação, a paginação e o enriquecimento com ``clickCount`` ao
  :class:`ListService` (Req 3.1, 3.2, 3.5, 3.6, 3.10, 3.11).
- Serializa o resultado em ``{ items, page, pageSize, total, totalPages }``.

Mapeamento de erros de domínio para HTTP (ver seção "Error Handling" do
design):

- :class:`ValidationError` → ``400`` (``page``/``pageSize`` inválido — Req 3.8,
  3.9).
- :class:`DataSourceError` → ``503`` (origem de dados indisponível — Req 3.12).

Todos os corpos de erro seguem o formato ``{ "error": "<mensagem>" }``.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from url_shortener.domain.errors import DataSourceError, ValidationError
from url_shortener.domain.validators import parse_pagination

#: Blueprint das rotas de listagem de URLs.
urls_bp = Blueprint("urls", __name__)


@urls_bp.get("/api/urls")
def list_urls():
    """Lista as URLs encurtadas de forma ordenada e paginada.

    Returns:
        Em caso de sucesso, uma tupla ``(payload, 200)`` com os campos
        ``items``, ``page``, ``pageSize``, ``total`` e ``totalPages``.
        Em caso de erro de validação dos parâmetros, ``(erro, 400)``; em caso
        de indisponibilidade da origem de dados, ``(erro, 503)``.
    """
    try:
        page, page_size = parse_pagination(
            request.args.get("page"),
            request.args.get("pageSize"),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    list_service = current_app.config["LIST_SERVICE"]

    try:
        result = list_service.list_urls(page, page_size)
    except DataSourceError as exc:
        return jsonify({"error": str(exc)}), 503

    return (
        jsonify(
            {
                "items": result.items,
                "page": result.page,
                "pageSize": result.page_size,
                "total": result.total,
                "totalPages": result.total_pages,
            }
        ),
        200,
    )
