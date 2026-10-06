"""Gerador do Short_Code do encurtador de URLs.

Componente puro (sem I/O direto) que gera o Short_Code alfanumérico de 7
caracteres (``[A-Za-z0-9]``) e garante unicidade consultando o repositório
através de um callable ``exists`` injetado.

A injeção de ``exists`` (um callable sobre o ``UrlRepository``) e da fonte
aleatória ``rng`` mantém o gerador testável sem Redis real (ver seção
"Code_Generator" do design).

Requisitos atendidos: 1.2 (7 caracteres alfanuméricos), 1.6 (reverificação de
unicidade em até 5 tentativas) e 1.9 (falha após 5 colisões).
"""

from __future__ import annotations

import secrets
import string
from typing import Callable

from url_shortener.domain.errors import CodeGenerationError

#: Alfabeto do Short_Code: [A-Za-z0-9], 62 símbolos.
ALPHABET = string.ascii_letters + string.digits

#: Comprimento fixo do Short_Code (Req 1.2).
CODE_LENGTH = 7

#: Número máximo de tentativas de geração ao buscar um código único (Req 1.6, 1.9).
MAX_RETRIES = 5


def generate_code(rng=secrets) -> str:
    """Gera um Short_Code aleatório de 7 caracteres de ``ALPHABET``.

    Args:
        rng: Fonte aleatória com um método ``choice(seq)`` (por padrão, o
            módulo ``secrets`` da stdlib). Injetável para tornar a geração
            determinística nos testes.

    Returns:
        Uma string de exatamente :data:`CODE_LENGTH` caracteres, todos
        pertencentes a ``[A-Za-z0-9]`` (Req 1.2).
    """
    return "".join(rng.choice(ALPHABET) for _ in range(CODE_LENGTH))


def generate_unique_code(exists: Callable[[str], bool], rng=secrets) -> str:
    """Gera um Short_Code único consultando ``exists``.

    Repete a geração até encontrar um código para o qual ``exists(code)``
    seja ``False``, em no máximo :data:`MAX_RETRIES` tentativas (Req 1.6).

    Args:
        exists: Callable que retorna ``True`` se o código já existir no
            Redis_Store (tipicamente ``UrlRepository.exists``).
        rng: Fonte aleatória injetável repassada a :func:`generate_code`.

    Returns:
        Um Short_Code que não existe no Redis_Store.

    Raises:
        CodeGenerationError: se todas as :data:`MAX_RETRIES` tentativas
            colidirem com códigos existentes (Req 1.9).
    """
    for _ in range(MAX_RETRIES):
        code = generate_code(rng)
        if not exists(code):
            return code

    raise CodeGenerationError(
        f"Não foi possível gerar um Short_Code único após {MAX_RETRIES} tentativas."
    )
