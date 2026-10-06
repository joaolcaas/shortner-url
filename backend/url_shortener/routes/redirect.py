"""Rota de redirecionamento do encurtador de URLs (``GET /:code``).

Traduz a requisição HTTP de redirecionamento em uma chamada ao
:class:`RedirectService`, monta a resposta 301 com o cabeçalho ``Location``
apontando para a Original_URL e, **após** a resposta estar montada, registra o
Click_Record no Analytics_Store (ver seção "Redirecionamento (GET /:code)" e
"Error Handling" do design).

Mapeamento de erros de domínio → status HTTP (Requisitos 2.2, 2.3, 2.4, 6.5):

- :class:`InvalidCodeError` (code fora do Code_Pattern, sem consultar o Redis)
  → ``404`` (Req 2.4).
- :class:`NotFoundError` (code inexistente no Redis_Store) → ``404`` (Req 2.2).
- :class:`GoneError` (code expirado) → ``410`` (Req 2.3, 6.5).

Registro de clique resiliente (Req 2.5, 2.6, 6.4): o ``record_click`` é
chamado depois de a resposta 301 ter sido construída e é envolvido em
``try/except`` que apenas registra log do erro. Qualquer falha de I/O no
SQLite não altera o status 301 nem o cabeçalho ``Location``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, request

from url_shortener.domain.errors import (
    GoneError,
    InvalidCodeError,
    NotFoundError,
)
from url_shortener.domain.models import ClickRecord

logger = logging.getLogger(__name__)

redirect_bp = Blueprint("redirect", __name__)


@redirect_bp.route("/<code>", methods=["GET"])
def redirect_to_original(code: str):
    """Redireciona ``code`` para a Original_URL correspondente.

    Resolve o Short_Code via :class:`RedirectService` e responde com 301 e o
    cabeçalho ``Location`` (Req 2.1). Em seguida registra o clique sem afetar a
    resposta (Req 2.5, 2.6, 6.4).

    Args:
        code: Short_Code recebido no caminho da requisição ``GET /:code``.

    Returns:
        Uma resposta 301 com ``Location`` para a Original_URL em caso de
        sucesso; ou um corpo JSON ``{"error": "<mensagem>"}`` com status 404
        (:class:`InvalidCodeError`/:class:`NotFoundError`) ou 410
        (:class:`GoneError`).
    """
    redirect_service = current_app.config["REDIRECT_SERVICE"]
    analytics_repository = current_app.config["ANALYTICS_REPOSITORY"]

    # Resolve o Short_Code; erros de domínio mapeiam para 404/410.
    try:
        original_url = redirect_service.resolve(code)
    except (InvalidCodeError, NotFoundError) as exc:
        return jsonify({"error": str(exc)}), 404
    except GoneError as exc:
        return jsonify({"error": str(exc)}), 410

    # Monta a resposta de redirecionamento 301 (Req 2.1).
    response = Response(status=301)
    response.headers["Location"] = original_url

    # Registro de clique resiliente (Req 2.5, 2.6, 6.4): acionado após a
    # resposta estar montada; qualquer falha apenas gera log e preserva o 301.
    try:
        click = ClickRecord(
            short_code=code,
            referrer=request.referrer,
            user_agent=request.user_agent.string if request.user_agent else None,
            ip=request.remote_addr,
            timestamp=datetime.now(timezone.utc),
        )
        analytics_repository.record_click(click)
    except Exception:  # noqa: BLE001 - falha no registro não afeta o 301.
        logger.exception("Falha ao registrar o clique para o code %s", code)

    return response
