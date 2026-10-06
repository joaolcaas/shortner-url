"""Erros de domínio do encurtador de URLs.

A lógica de negócio lança estes erros; a camada de rotas os traduz para o
status HTTP correto (ver seção "Error Handling" do design). Todos os corpos
de erro seguem o formato ``{ "error": "<mensagem>" }``.

Mapeamento erro de domínio → status HTTP:

| Erro                 | Status HTTP | Requisitos                     |
|----------------------|-------------|--------------------------------|
| ValidationError      | 400         | 1.3, 1.4, 1.7, 1.8, 3.8, 3.9, 4.5 |
| NotFoundError        | 404         | 2.2, 4.4                       |
| InvalidCodeError     | 404         | 2.4                            |
| GoneError            | 410         | 2.3, 6.5                       |
| CodeGenerationError  | 500         | 1.9                            |
| PersistenceError     | 500         | 6.2                            |
| DataSourceError      | 503         | 3.12                           |
"""


class DomainError(Exception):
    """Classe base para todos os erros de domínio."""


class ValidationError(DomainError):
    """Dados de entrada inválidos.

    Causas: URL ausente/vazia, esquema diferente de http/https ou sem host
    (Req 1.3, 1.4); ``expiresAt`` com formato inválido ou instante não futuro
    (Req 1.7, 1.8); ``code`` fora do Code_Pattern em estatísticas (Req 4.5);
    ``page``/``pageSize`` não numérico ou menor que 1 (Req 3.8, 3.9).

    Mapeado para HTTP 400.
    """


class NotFoundError(DomainError):
    """Short_Code inexistente.

    Causas: redirecionamento para code ausente no Redis_Store (Req 2.2);
    estatísticas de code inexistente (Req 4.4).

    Mapeado para HTTP 404.
    """


class InvalidCodeError(DomainError):
    """Short_Code fora do Code_Pattern no redirecionamento (Req 2.4).

    Levantado antes de qualquer consulta ao Redis_Store.

    Mapeado para HTTP 404.
    """


class GoneError(DomainError):
    """Short_Code expirado: ``expiresAt`` anterior ao instante atual
    (Req 2.3, 6.5).

    Mapeado para HTTP 410.
    """


class CodeGenerationError(DomainError):
    """Não foi possível gerar um Short_Code único após 5 tentativas (Req 1.9).

    Mapeado para HTTP 500.
    """


class PersistenceError(DomainError):
    """Falha ao gravar o mapeamento no Redis_Store (Req 6.2).

    Mapeado para HTTP 500.
    """


class DataSourceError(DomainError):
    """Origem de dados indisponível durante a listagem de URLs (Req 3.12).

    Mapeado para HTTP 503.
    """
