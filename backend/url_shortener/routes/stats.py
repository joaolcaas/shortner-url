"""Rota de estatísticas de uma URL encurtada (``GET /api/stats/:code``).

Traduz a requisição HTTP em uma chamada ao :class:`StatsService`, serializa o
resultado em JSON e mapeia os erros de domínio para o status HTTP correto (ver
o contrato de ``GET /api/stats/:code`` e a seção "Error Handling" do design).

O ``StatsService`` é obtido do contexto da aplicação Flask
(``current_app.config["STATS_SERVICE"]``), cuja fiação é feita pela fábrica da
aplicação (``create_app``). A rota não contém regra de negócio.

Mapeamento de resultados (Requisito 4):

- 200 OK com ``totalClicks``, ``clicksByDay`` e ``topReferrers`` (Req 4.1–4.3,
  4.6).
- 400 Bad Request quando o code está fora do Code_Pattern
  (:class:`ValidationError` — Req 4.5).
- 404 Not Found quando o code não existe (:class:`NotFoundError` — Req 4.4).

Todos os corpos de erro seguem o formato ``{ "error": "<mensagem>" }``.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from url_shortener.domain.errors import NotFoundError, ValidationError

#: Blueprint das rotas de estatísticas.
stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/stats/<code>", methods=["GET"])
def get_stats(code: str):
    """Retorna as estatísticas de acesso de um Short_Code.

    Args:
        code: Short_Code recebido no path da requisição.

    Returns:
        - 200 com ``{"totalClicks", "clicksByDay", "topReferrers"}`` quando o
          code existe (Req 4.1–4.3, 4.6).
        - 400 com ``{"error": "<mensagem>"}`` quando o code está fora do
          Code_Pattern (Req 4.5).
        - 404 com ``{"error": "<mensagem>"}`` quando o code não existe
          (Req 4.4).
    """
    stats_service = current_app.config["STATS_SERVICE"]

    try:
        stats = stats_service.get_stats(code)
    except ValidationError as error:
        return jsonify({"error": str(error)}), 400
    except NotFoundError as error:
        return jsonify({"error": str(error)}), 404

    return jsonify(stats), 200
