"""Repositório de URLs encurtadas no Redis (``Redis_Store``).

Encapsula o acesso ao Redis e expõe métodos de domínio para o mapeamento
``Short_Code → metadados`` (ver seção "UrlRepository" do design).

Esquema de chaves:

| Chave             | Tipo       | Conteúdo                                             |
|-------------------|------------|------------------------------------------------------|
| ``url:{code}``    | Hash       | ``originalUrl``, ``createdAt`` (ISO 8601 UTC),       |
|                   |            | ``expiresAt`` (ISO 8601 UTC ou vazio)                |
| ``urls:index``    | Sorted Set | membro = ``shortCode``, score = epoch de ``createdAt`` |

``createdAt`` e ``expiresAt`` são persistidos em ISO 8601 UTC. O índice
``urls:index`` suporta a recuperação dos códigos ordenados por data de criação
para a listagem paginada (``GET /api/urls``).

Requisitos atendidos: 1.1 (persistir mapeamento), 3.12 (``DataSourceError`` em
indisponibilidade), 6.1 (gravação no Redis) e 6.2 (``PersistenceError`` em
falha de gravação).
"""

from __future__ import annotations

from datetime import datetime, timezone

from url_shortener.domain.errors import DataSourceError, PersistenceError
from url_shortener.domain.models import UrlMapping

#: Prefixo das chaves de Hash do mapeamento principal.
_KEY_PREFIX = "url:"

#: Chave do Sorted Set que indexa os códigos por epoch de ``createdAt``.
_INDEX_KEY = "urls:index"


def _key(code: str) -> str:
    """Monta a chave do Hash do mapeamento para ``code``."""
    return f"{_KEY_PREFIX}{code}"


def _to_iso(value: datetime) -> str:
    """Serializa um ``datetime`` para ISO 8601 em UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    """Faz o parse de um timestamp ISO 8601 persistido, garantindo UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decode(value) -> str:
    """Normaliza valores vindos do Redis para ``str``.

    Dependendo do cliente/configuração, o Redis pode devolver ``bytes`` ou
    ``str``; esta função cobre ambos os casos.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


class UrlRepository:
    """Repositório do mapeamento de URLs encurtadas sobre o Redis."""

    def __init__(self, redis_client):
        """Inicializa o repositório.

        Args:
            redis_client: Cliente Redis (ex.: ``redis.Redis`` ou um
                ``fakeredis`` nos testes).
        """
        self._redis = redis_client

    def exists(self, code: str) -> bool:
        """Indica se já existe um mapeamento para ``code``.

        Checa a existência da chave ``url:{code}`` (usada pelo Code_Generator
        para garantir unicidade — Req 1.6).

        Args:
            code: Short_Code a verificar.

        Returns:
            ``True`` se a chave existir, ``False`` caso contrário.
        """
        return bool(self._redis.exists(_key(code)))

    def save_mapping(self, mapping: UrlMapping) -> None:
        """Grava o mapeamento no Redis_Store (Req 1.1, 6.1).

        Persiste o Hash ``url:{shortCode}`` com ``originalUrl``, ``createdAt``
        e ``expiresAt`` (ISO 8601 UTC; vazio quando não há expiração) e
        adiciona o ``shortCode`` ao Sorted Set ``urls:index`` com score igual
        ao epoch de ``createdAt``.

        Args:
            mapping: O :class:`UrlMapping` a persistir.

        Raises:
            PersistenceError: se qualquer operação de gravação no Redis
                falhar (Req 6.2).
        """
        created_at = (
            mapping.created_at.replace(tzinfo=timezone.utc)
            if mapping.created_at.tzinfo is None
            else mapping.created_at.astimezone(timezone.utc)
        )
        fields = {
            "originalUrl": mapping.original_url,
            "createdAt": _to_iso(mapping.created_at),
            "expiresAt": _to_iso(mapping.expires_at) if mapping.expires_at else "",
        }
        try:
            self._redis.hset(_key(mapping.short_code), mapping=fields)
            self._redis.zadd(
                _INDEX_KEY, {mapping.short_code: created_at.timestamp()}
            )
        except Exception as exc:  # noqa: BLE001 - encapsula falha de I/O do Redis
            raise PersistenceError(
                "Não foi possível persistir a URL encurtada."
            ) from exc

    def get_mapping(self, code: str) -> UrlMapping | None:
        """Recupera o mapeamento associado a ``code``.

        Args:
            code: Short_Code a buscar.

        Returns:
            O :class:`UrlMapping` correspondente, ou ``None`` se o code não
            existir no Redis_Store.
        """
        data = self._redis.hgetall(_key(code))
        if not data:
            return None

        data = {_decode(k): _decode(v) for k, v in data.items()}

        expires_raw = data.get("expiresAt") or ""
        expires_at = _from_iso(expires_raw) if expires_raw else None

        return UrlMapping(
            short_code=code,
            original_url=data["originalUrl"],
            created_at=_from_iso(data["createdAt"]),
            expires_at=expires_at,
        )

    def list_mappings(self) -> list[UrlMapping]:
        """Retorna todos os mapeamentos para ordenação/paginação em memória.

        Percorre o índice ``urls:index`` e recupera cada mapeamento. A
        ordenação decrescente final e o desempate por ``shortCode`` são
        aplicados na camada de serviço (Req 3.2).

        Returns:
            Lista de :class:`UrlMapping` existentes (pode ser vazia).

        Raises:
            DataSourceError: se o Redis estiver indisponível ou a leitura
                falhar (Req 3.12).
        """
        try:
            codes = self._redis.zrange(_INDEX_KEY, 0, -1)
            mappings: list[UrlMapping] = []
            for raw_code in codes:
                code = _decode(raw_code)
                mapping = self.get_mapping(code)
                if mapping is not None:
                    mappings.append(mapping)
            return mappings
        except Exception as exc:  # noqa: BLE001 - encapsula indisponibilidade do Redis
            raise DataSourceError(
                "Falha temporária ao recuperar as URLs encurtadas."
            ) from exc
