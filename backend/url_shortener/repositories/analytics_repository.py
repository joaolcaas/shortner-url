"""Repositório de analytics no SQLite (``Analytics_Store``).

Encapsula o acesso ao banco SQLite que mantém os ``Click_Records``. As
consultas de analytics exigem agregações (contagem por dia, top referrers),
para as quais um banco relacional com SQL é mais adequado (ver seção
"AnalyticsRepository" e "Esquema do SQLite" do design).

O construtor recebe uma conexão ``sqlite3`` já aberta. O schema (tabela
``clicks`` e índices) é criado de forma idempotente na inicialização.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from url_shortener.domain.models import ClickRecord, DayCount, ReferrerCount


class AnalyticsRepository:
    """Repositório dos ``Click_Records`` persistidos no SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Cria a tabela ``clicks`` e seus índices, se ainda não existirem."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clicks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT    NOT NULL,
                referrer   TEXT,
                user_agent TEXT,
                ip         TEXT,
                timestamp  TEXT    NOT NULL   -- ISO 8601 UTC
            );

            CREATE INDEX IF NOT EXISTS idx_clicks_code
                ON clicks (short_code);
            CREATE INDEX IF NOT EXISTS idx_clicks_code_time
                ON clicks (short_code, timestamp);
            """
        )
        self._conn.commit()

    def record_click(self, click: ClickRecord) -> None:
        """Insere um ``Click_Record`` no Analytics_Store (Req 2.5, 6.3).

        No fluxo de redirecionamento o chamador trata/ignora eventuais falhas
        de I/O (Req 2.6, 6.4); este método não as suprime.
        """
        self._conn.execute(
            """
            INSERT INTO clicks (short_code, referrer, user_agent, ip, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                click.short_code,
                click.referrer,
                click.user_agent,
                click.ip,
                click.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def count_clicks(self, code: str) -> int:
        """Retorna o ``Click_Count`` do code (inteiro >= 0)."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM clicks WHERE short_code = ?",
            (code,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def count_clicks_bulk(self, codes: list[str]) -> dict[str, int]:
        """Retorna a contagem de cliques por code para a listagem paginada.

        Codes sem cliques recebem contagem 0 no dicionário resultante.
        """
        result: dict[str, int] = {code: 0 for code in codes}
        if not codes:
            return result

        placeholders = ",".join("?" for _ in codes)
        rows = self._conn.execute(
            f"""
            SELECT short_code, COUNT(*)
            FROM clicks
            WHERE short_code IN ({placeholders})
            GROUP BY short_code
            """,
            tuple(codes),
        ).fetchall()
        for short_code, count in rows:
            result[short_code] = int(count)
        return result

    def clicks_by_day(self, code: str, since: datetime) -> list[DayCount]:
        """Cliques agrupados por dia desde ``since``, crescente por data (Req 4.2)."""
        rows = self._conn.execute(
            """
            SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS count
            FROM clicks
            WHERE short_code = ? AND timestamp >= ?
            GROUP BY day
            ORDER BY day ASC
            """,
            (code, since.isoformat()),
        ).fetchall()
        return [DayCount(date=day, count=int(count)) for day, count in rows]

    def top_referrers(self, code: str, limit: int = 10) -> list[ReferrerCount]:
        """Top referrers por contagem, decrescente, no máximo ``limit`` (Req 4.3)."""
        rows = self._conn.execute(
            """
            SELECT referrer, COUNT(*) AS count
            FROM clicks
            WHERE short_code = ? AND referrer IS NOT NULL
            GROUP BY referrer
            ORDER BY count DESC, referrer ASC
            LIMIT ?
            """,
            (code, limit),
        ).fetchall()
        return [ReferrerCount(referrer=referrer, count=int(count)) for referrer, count in rows]
