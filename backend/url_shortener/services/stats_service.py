"""Serviço de estatísticas de uma URL encurtada (``GET /api/stats/:code``).

Orquestra a validação do ``Code_Pattern``, a verificação de existência do
Short_Code e o cálculo das estatísticas de acesso (ver seção "StatsService" e
o contrato de ``GET /api/stats/:code`` do design).

Fluxo (Requisito 4):

1. Validar o ``Code_Pattern`` antes de qualquer I/O; code fora do padrão
   (vazio ou fora de ``[A-Za-z0-9]{1,16}``) lança :class:`ValidationError`
   (Req 4.5 → HTTP 400).
2. Verificar a existência do code no ``Redis_Store``; code inexistente lança
   :class:`NotFoundError` (Req 4.4 → HTTP 404).
3. Calcular ``totalClicks`` (Req 4.1), ``clicksByDay`` dos últimos 30 dias em
   ordem crescente (Req 4.2) e ``topReferrers`` com no máximo 10 itens em ordem
   decrescente de contagem (Req 4.3).
4. Quando o code existe mas não possui cliques, retornar ``totalClicks`` igual
   a 0 e ``clicksByDay``/``topReferrers`` como listas vazias (Req 4.6).

O resultado é um ``dict`` pronto para serialização pela camada de rotas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from url_shortener.domain.errors import NotFoundError, ValidationError
from url_shortener.domain.validators import validate_code_pattern
from url_shortener.repositories.analytics_repository import AnalyticsRepository
from url_shortener.repositories.url_repository import UrlRepository

#: Janela considerada para ``clicksByDay`` (últimos 30 dias — Req 4.2).
_CLICKS_WINDOW_DAYS = 30

#: Número máximo de referrers retornados em ``topReferrers`` (Req 4.3).
_TOP_REFERRERS_LIMIT = 10


class StatsService:
    """Calcula as estatísticas de acesso de um Short_Code existente."""

    def __init__(
        self,
        url_repository: UrlRepository,
        analytics_repository: AnalyticsRepository,
    ) -> None:
        """Inicializa o serviço.

        Args:
            url_repository: Repositório do mapeamento de URLs (Redis), usado
                para verificar a existência do Short_Code.
            analytics_repository: Repositório de analytics (SQLite), usado para
                calcular ``totalClicks``, ``clicksByDay`` e ``topReferrers``.
        """
        self._urls = url_repository
        self._analytics = analytics_repository

    def get_stats(self, code: str, now: datetime | None = None) -> dict:
        """Retorna as estatísticas de acesso do Short_Code.

        Args:
            code: Short_Code recebido na requisição.
            now: Instante atual de referência (injetável para testes). Quando
                ausente, usa o horário atual do servidor em UTC.

        Returns:
            Um ``dict`` com as chaves:

            - ``totalClicks`` (``int`` >= 0): total de cliques do code.
            - ``clicksByDay`` (``list[dict]``): itens ``{"date", "count"}`` dos
              últimos 30 dias, em ordem crescente de data.
            - ``topReferrers`` (``list[dict]``): itens ``{"referrer", "count"}``,
              no máximo 10, em ordem decrescente de contagem.

        Raises:
            ValidationError: se ``code`` for vazio ou estiver fora do
                Code_Pattern (Req 4.5 → HTTP 400).
            NotFoundError: se ``code`` não existir no Redis_Store
                (Req 4.4 → HTTP 404).
        """
        if not validate_code_pattern(code):
            raise ValidationError("O Short_Code é inválido.")

        if not self._urls.exists(code):
            raise NotFoundError("Short_Code não encontrado.")

        reference = self._normalize_now(now)
        since = reference - timedelta(days=_CLICKS_WINDOW_DAYS)

        total_clicks = self._analytics.count_clicks(code)
        clicks_by_day = self._analytics.clicks_by_day(code, since)
        top_referrers = self._analytics.top_referrers(
            code, limit=_TOP_REFERRERS_LIMIT
        )

        return {
            "totalClicks": total_clicks,
            "clicksByDay": [
                {"date": day.date, "count": day.count} for day in clicks_by_day
            ],
            "topReferrers": [
                {"referrer": ref.referrer, "count": ref.count}
                for ref in top_referrers
            ],
        }

    @staticmethod
    def _normalize_now(now: datetime | None) -> datetime:
        """Normaliza o instante de referência para UTC."""
        if now is None:
            return datetime.now(timezone.utc)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
