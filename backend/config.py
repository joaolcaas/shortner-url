"""Configuração do backend do encurtador de URLs.

Define as chaves de configuração usadas pela fábrica da aplicação:
- BASE_URL: domínio base usado para montar a Short_URL.
- REDIS_URL: URL de conexão com o Redis_Store (mapeamento de URLs).
- SQLITE_PATH: caminho do arquivo SQLite do Analytics_Store (cliques).
"""

import os


class Config:
    """Configuração base da aplicação."""

    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    SQLITE_PATH = os.environ.get("SQLITE_PATH", "analytics.db")
