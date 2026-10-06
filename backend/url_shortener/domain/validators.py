"""Validadores de domínio do encurtador de URLs.

Componentes puros (sem I/O) reutilizados pelos serviços. Validam a URL
submetida ao encurtamento, o formato de um Short_Code recebido em requisições,
o campo ``expiresAt`` e os parâmetros de paginação.

Erros de validação são sinalizados por :class:`ValidationError`
(ver seção "Error Handling" do design), traduzido para HTTP 400 pela camada
de rotas.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from url_shortener.domain.errors import ValidationError

#: Esquemas de URL aceitos para encurtamento (comparação case-insensitive).
ALLOWED_SCHEMES = ("http", "https")

#: Code_Pattern: 1 a 16 caracteres alfanuméricos (``[A-Za-z0-9]{1,16}``).
CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")


def validate_url(url: str | None) -> str:
    """Valida uma URL submetida para encurtamento.

    A URL deve ser não vazia, utilizar o esquema ``http`` ou ``https``
    (comparação case-insensitive) e possuir um host válido. Em caso de
    sucesso, retorna a URL normalizada (sem espaços nas extremidades).

    Args:
        url: URL fornecida pelo usuário (pode ser ``None``).

    Returns:
        A URL normalizada.

    Raises:
        ValidationError: se a URL for vazia/nula/sem host (Req 1.4, 5.3) ou
            se o esquema não for ``http``/``https`` (Req 1.3, 5.2).
    """
    if url is None:
        raise ValidationError("A URL é obrigatória.")

    normalized = url.strip()
    if not normalized:
        raise ValidationError("A URL é obrigatória.")

    parsed = urlparse(normalized)

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValidationError(
            "O esquema da URL não é suportado; utilize http ou https."
        )

    if not parsed.netloc or not parsed.hostname:
        raise ValidationError("A URL é inválida: host ausente.")

    return normalized


def validate_code_pattern(code: str) -> bool:
    """Verifica se um Short_Code recebido casa com o Code_Pattern.

    O Code_Pattern é definido como uma sequência de 1 a 16 caracteres
    alfanuméricos (``[A-Za-z0-9]{1,16}``). Esta checagem é usada antes de
    qualquer I/O no redirecionamento (Req 2.4) e nas estatísticas (Req 4.5),
    permitindo rejeitar codes malformados sem consultar o Redis_Store.

    Args:
        code: Short_Code recebido na requisição.

    Returns:
        ``True`` se ``code`` casa com o Code_Pattern; ``False`` caso contrário
        (inclusive para ``code`` vazio ou ``None``).
    """
    if not code:
        return False

    return CODE_PATTERN.fullmatch(code) is not None


def parse_expires_at(value: str | None, now: datetime) -> datetime | None:
    """Faz parse e valida o campo ``expiresAt`` do encurtamento.

    Quando ``value`` está ausente (``None`` ou string vazia/em branco), a URL
    não possui expiração e a função retorna ``None``. Caso contrário, interpreta
    ``value`` como uma data/hora ISO 8601 e exige que represente um instante
    estritamente futuro em relação a ``now``.

    Datas são tratadas em UTC: um valor sem offset de fuso é assumido como UTC,
    e um valor com offset é convertido para UTC antes da comparação.

    Args:
        value: Valor de ``expiresAt`` fornecido pelo usuário (ISO 8601) ou
            ``None`` quando ausente.
        now: Instante atual do servidor usado como referência de comparação.

    Returns:
        O :class:`datetime` em UTC quando ``value`` representa um instante
        futuro válido; ``None`` quando ``value`` está ausente.

    Raises:
        ValidationError: se ``value`` não for uma data ISO 8601 válida
            (Req 1.7) ou se o instante for igual ou anterior a ``now``
            (Req 1.8).
    """
    if value is None:
        return None

    if isinstance(value, str) and not value.strip():
        return None

    raw = value.strip() if isinstance(value, str) else value

    # Suporta o sufixo "Z" (UTC), que datetime.fromisoformat só aceita a
    # partir do Python 3.11; normaliza para o offset "+00:00".
    if isinstance(raw, str) and raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(raw)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "O formato da data de expiração é inválido; utilize ISO 8601."
        ) from exc

    # Datas ingênuas (sem fuso) são assumidas como UTC; datas com fuso são
    # convertidas para UTC para uma comparação consistente.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    reference = now
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    else:
        reference = reference.astimezone(timezone.utc)

    if parsed <= reference:
        raise ValidationError("A data de expiração deve ser futura.")

    return parsed


#: Valor padrão de ``page`` quando o query param está ausente (Req 3.3).
DEFAULT_PAGE = 1

#: Valor padrão de ``pageSize`` quando o query param está ausente (Req 3.4).
DEFAULT_PAGE_SIZE = 50

#: Limite máximo de ``pageSize`` (Req 3.7).
MAX_PAGE_SIZE = 100


def _parse_positive_int(raw: object, field: str) -> int:
    """Interpreta um parâmetro de paginação como inteiro positivo (``>= 1``).

    Aceita inteiros já tipados ou strings numéricas (com espaços nas
    extremidades toleradas). Valores não numéricos, fracionários ou menores
    que 1 são rejeitados.

    Args:
        raw: Valor bruto do parâmetro (string de query param, inteiro ou outro).
        field: Nome do parâmetro (``"page"`` ou ``"pageSize"``) usado na
            mensagem de erro.

    Returns:
        O inteiro correspondente, garantidamente ``>= 1``.

    Raises:
        ValidationError: se ``raw`` não for numérico ou for menor que 1.
    """
    # ``bool`` é subclasse de ``int``; tratá-lo como não numérico evita que
    # ``True``/``False`` sejam aceitos como 1/0.
    if isinstance(raw, bool):
        raise ValidationError(f"O parâmetro {field} é inválido.")

    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            raise ValidationError(f"O parâmetro {field} é inválido.")
        try:
            value = int(candidate)
        except ValueError as exc:
            raise ValidationError(f"O parâmetro {field} é inválido.") from exc
    else:
        raise ValidationError(f"O parâmetro {field} é inválido.")

    if value < 1:
        raise ValidationError(f"O parâmetro {field} é inválido.")

    return value


def parse_pagination(page_raw: object, page_size_raw: object) -> tuple[int, int]:
    """Faz parse e valida os parâmetros de paginação da listagem de URLs.

    Quando um parâmetro está ausente (``None``), aplica o valor padrão
    (``page=1``, ``pageSize=50`` — Req 3.3, 3.4). O ``pageSize`` resultante é
    limitado a 100 (Req 3.7). Parâmetros fornecidos devem ser inteiros
    positivos (``>= 1``); valores não numéricos ou menores que 1 são
    rejeitados (Req 3.8, 3.9).

    Args:
        page_raw: Valor bruto do query param ``page`` (string, inteiro ou
            ``None`` quando ausente).
        page_size_raw: Valor bruto do query param ``pageSize`` (string, inteiro
            ou ``None`` quando ausente).

    Returns:
        Uma tupla ``(page, page_size)`` com inteiros válidos, onde
        ``page_size`` já respeita o limite máximo de 100.

    Raises:
        ValidationError: se ``page`` for não numérico ou menor que 1 (Req 3.8),
            ou se ``pageSize`` for não numérico ou menor que 1 (Req 3.9).
    """
    if page_raw is None:
        page = DEFAULT_PAGE
    else:
        page = _parse_positive_int(page_raw, "page")

    if page_size_raw is None:
        page_size = DEFAULT_PAGE_SIZE
    else:
        page_size = _parse_positive_int(page_size_raw, "pageSize")

    if page_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE

    return page, page_size
