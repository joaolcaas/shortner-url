"""Serviço de encurtamento de URLs (``ShortenService``).

Orquestra a lógica de negócio do encurtamento (ver seções "Serviços" e o fluxo
"Encurtamento (POST /api/shorten)" do design):

1. Valida a URL submetida (:func:`validate_url`).
2. Faz parse e valida o campo ``expiresAt`` (:func:`parse_expires_at`), exigindo
   um instante futuro quando fornecido.
3. Gera um Short_Code único consultando o repositório
   (:func:`generate_unique_code`, até 5 tentativas).
4. Monta o :class:`UrlMapping` com ``created_at`` no instante atual (UTC).
5. Persiste o mapeamento no Redis_Store (``UrlRepository.save_mapping``).

Erros de domínio são propagados ao chamador (a camada de rotas os traduz para o
status HTTP correto):

- :class:`ValidationError` — URL inválida (Req 1.3, 1.4) ou ``expiresAt``
  inválido/não futuro (Req 1.7, 1.8).
- :class:`CodeGenerationError` — sem Short_Code único após 5 tentativas (Req 1.9).
- :class:`PersistenceError` — falha ao gravar no Redis_Store (Req 6.2).

Requisitos atendidos: 1.1, 1.5, 1.6, 1.9, 6.2.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from url_shortener.domain.code_generator import generate_unique_code
from url_shortener.domain.models import UrlMapping
from url_shortener.domain.validators import parse_expires_at, validate_url
from url_shortener.repositories.url_repository import UrlRepository


class ShortenService:
    """Orquestra o encurtamento de uma URL em um Short_Code persistido."""

    def __init__(self, url_repository: UrlRepository, rng=secrets):
        """Inicializa o serviço.

        Args:
            url_repository: Repositório do ``Redis_Store`` usado para verificar
                a unicidade do code (``exists``) e persistir o mapeamento
                (``save_mapping``).
            rng: Fonte aleatória injetável repassada ao gerador de código
                (por padrão, o módulo ``secrets`` da stdlib). Facilita tornar a
                geração determinística nos testes.
        """
        self._url_repository = url_repository
        self._rng = rng

    def shorten(self, url: str | None, expires_at: str | None = None) -> UrlMapping:
        """Encurta ``url`` e persiste o mapeamento, retornando-o.

        Args:
            url: URL original fornecida pelo usuário (``http``/``https``).
            expires_at: Valor opcional de ``expiresAt`` em ISO 8601. Quando
                ausente, a URL não possui expiração.

        Returns:
            O :class:`UrlMapping` persistido, com ``created_at`` no instante
            atual (UTC) e o Short_Code gerado.

        Raises:
            ValidationError: se a URL for inválida (Req 1.3, 1.4) ou se
                ``expires_at`` tiver formato inválido ou não for futuro
                (Req 1.7, 1.8).
            CodeGenerationError: se não houver Short_Code único após 5
                tentativas (Req 1.9).
            PersistenceError: se a gravação no Redis_Store falhar (Req 6.2).
        """
        now = datetime.now(timezone.utc)

        # 1. Valida a URL (Req 1.1, 1.3, 1.4). Lança ValidationError se inválida.
        normalized_url = validate_url(url)

        # 2. Faz parse/valida expiresAt (Req 1.5, 1.7, 1.8). None quando ausente.
        parsed_expires_at = parse_expires_at(expires_at, now)

        # 3. Gera um Short_Code único (Req 1.6, 1.9). Lança CodeGenerationError
        #    se todas as tentativas colidirem.
        code = generate_unique_code(self._url_repository.exists, rng=self._rng)

        # 4. Monta o mapeamento com created_at no instante atual (UTC).
        mapping = UrlMapping(
            short_code=code,
            original_url=normalized_url,
            created_at=now,
            expires_at=parsed_expires_at,
        )

        # 5. Persiste no Redis_Store (Req 1.1, 6.2). Lança PersistenceError em
        #    falha de gravação.
        self._url_repository.save_mapping(mapping)

        return mapping
