"""Rota de encurtamento de URLs (``POST /api/shorten``).

Traduz a requisição HTTP em uma chamada ao :class:`ShortenService`, serializa a
resposta de sucesso (201) e mapeia os erros de domínio para o status HTTP
correto (ver seções "Contratos da API" e "Error Handling" do design):

- Sucesso: 201 com ``shortCode``, ``shortUrl``, ``originalUrl``, ``createdAt`` e
  ``expiresAt`` (datas em ISO 8601 UTC; ``expiresAt`` é ``null`` quando ausente).
- :class:`ValidationError` → 400 (URL ausente/vazia, esquema inválido ou sem
  host — Req 1.3, 1.4; ``expiresAt`` com formato inválido ou não futuro —
  Req 1.7, 1.8).
- :class:`CodeGenerationError` → 500 (sem Short_Code único após 5 tentativas —
  Req 1.9).
- :class:`PersistenceError` → 500 (falha ao gravar no Redis_Store — Req 6.2).

Corpos de erro seguem o formato ``{ "error": "<mensagem>" }``.

O blueprint obtém o :class:`ShortenService` e a ``BASE_URL`` do contexto da
aplicação Flask (``current_app.config``). A fábrica da aplicação (``create_app``)
é responsável por preencher ``current_app.config['SHORTEN_SERVICE']`` e
``current_app.config['BASE_URL']``.

Requisitos atendidos: 1.1, 1.3, 1.4, 1.7, 1.8, 1.9, 6.2.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from url_shortener.domain.errors import (
    CodeGenerationError,
    PersistenceError,
    ValidationError,
)
from url_shortener.domain.models import UrlMapping

shorten_bp = Blueprint("shorten", __name__)


def _to_iso_utc(value: datetime | None) -> str | None:
    """Serializa um ``datetime`` para ISO 8601 em UTC com sufixo ``Z``.

    Retorna ``None`` quando ``value`` é ``None`` (ex.: ``expiresAt`` ausente).
    Datas sem timezone (naive) são assumidas em UTC; datas com timezone são
    convertidas para UTC antes de serializar.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    # Formato "2025-01-10T12:00:00Z": segundos de precisão, sufixo Z em vez de +00:00.
    return value.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _serialize_mapping(mapping: UrlMapping, base_url: str) -> dict:
    """Monta o corpo de resposta 201 a partir do mapeamento persistido."""
    short_url = base_url.rstrip("/") + "/" + mapping.short_code
    return {
        "shortCode": mapping.short_code,
        "shortUrl": short_url,
        "originalUrl": mapping.original_url,
        "createdAt": _to_iso_utc(mapping.created_at),
        "expiresAt": _to_iso_utc(mapping.expires_at),
    }


@shorten_bp.route("/api/shorten", methods=["POST"])
def shorten():
    """Encurta a URL recebida no corpo da requisição.

    Corpo esperado: ``{ "url": string, "expiresAt"?: string (ISO 8601) }``.

    Returns:
        - 201 com o mapeamento serializado em caso de sucesso.
        - 400 (``ValidationError``) para URL/``expiresAt`` inválidos.
        - 500 (``CodeGenerationError``/``PersistenceError``) para falha de
          geração de code único ou de persistência.
    """
    service = current_app.config["SHORTEN_SERVICE"]
    base_url = current_app.config["BASE_URL"]

    # Corpo ausente ou JSON malformado resulta em dados inválidos → 400.
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Corpo da requisição deve ser um objeto JSON."}), 400

    url = body.get("url")
    expires_at = body.get("expiresAt")

    try:
        mapping = service.shorten(url, expires_at)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (CodeGenerationError, PersistenceError) as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(_serialize_mapping(mapping, base_url)), 201
