"""Serviço de redirecionamento do encurtador de URLs.

Resolve um Short_Code recebido em ``GET /:code`` para a Original_URL
correspondente, aplicando a validação do Code_Pattern antes de qualquer I/O
e verificando a expiração do mapeamento (ver seção "RedirectService" do
design).

Ordem de resolução (Requisitos 2.1, 2.2, 2.3, 2.4, 6.5):

1. Validar o Code_Pattern **antes** de consultar o Redis_Store; code fora do
   padrão → :class:`InvalidCodeError` (Req 2.4), sem qualquer I/O.
2. Buscar o mapeamento no Redis_Store; code inexistente →
   :class:`NotFoundError` (Req 2.2).
3. Verificar a expiração; ``expiresAt`` anterior ao instante atual →
   :class:`GoneError` (Req 2.3, 6.5).
4. Retornar a Original_URL para o redirecionamento 301 (Req 2.1).

O registro do Click_Record é responsabilidade da camada de rotas, acionado
após o envio da resposta de redirecionamento (Req 2.5, 2.6) e, portanto, não
faz parte deste serviço.
"""

from __future__ import annotations

from datetime import datetime, timezone

from url_shortener.domain.errors import (
    GoneError,
    InvalidCodeError,
    NotFoundError,
)
from url_shortener.domain.validators import validate_code_pattern
from url_shortener.repositories.url_repository import UrlRepository


class RedirectService:
    """Resolve um Short_Code para a Original_URL do redirecionamento."""

    def __init__(self, url_repository: UrlRepository):
        """Inicializa o serviço.

        Args:
            url_repository: Repositório do mapeamento de URLs sobre o Redis
                (:class:`UrlRepository`).
        """
        self._urls = url_repository

    def resolve(self, code: str, now: datetime | None = None) -> str:
        """Resolve ``code`` para a Original_URL correspondente.

        Valida o Code_Pattern antes de qualquer acesso ao Redis_Store, busca o
        mapeamento, verifica a expiração e devolve a Original_URL.

        Args:
            code: Short_Code recebido na requisição ``GET /:code``.
            now: Instante atual usado para a verificação de expiração; quando
                ``None``, utiliza o horário atual do servidor em UTC.

        Returns:
            A Original_URL associada a ``code``, para o redirecionamento 301
            (Req 2.1).

        Raises:
            InvalidCodeError: se ``code`` estiver fora do Code_Pattern
                (Req 2.4); levantado sem consultar o Redis_Store.
            NotFoundError: se ``code`` não existir no Redis_Store (Req 2.2).
            GoneError: se o mapeamento estiver expirado — ``expiresAt`` igual
                ou anterior ao instante atual (Req 2.3, 6.5).
        """
        # 1. Valida o Code_Pattern antes de qualquer I/O (Req 2.4).
        if not validate_code_pattern(code):
            raise InvalidCodeError("O código informado é inválido.")

        # 2. Busca o mapeamento no Redis_Store (Req 2.2).
        mapping = self._urls.get_mapping(code)
        if mapping is None:
            raise NotFoundError("O código informado não foi encontrado.")

        # 3. Verifica a expiração (Req 2.3, 6.5).
        if mapping.expires_at is not None:
            reference = now if now is not None else datetime.now(timezone.utc)
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            else:
                reference = reference.astimezone(timezone.utc)

            expires_at = mapping.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            else:
                expires_at = expires_at.astimezone(timezone.utc)

            if expires_at <= reference:
                raise GoneError("O link expirou.")

        # 4. Retorna a Original_URL para o redirecionamento 301 (Req 2.1).
        return mapping.original_url
