from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.course import Course
from app.domain.repositories.search_repository import SearchRepository


def _build_match_query(query: str) -> str:
    """Turn free text into a safe FTS5 prefix query (quoted tokens, OR-joined)."""
    tokens = [token for token in query.replace('"', " ").split() if token]
    return " OR ".join(f'"{token}"*' for token in tokens)


class Fts5SearchRepository(SearchRepository):
    """Full-text search over the `courses_fts` virtual table (SQLite, phase 1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_active(self, query: str, limit: int = 20) -> list[Course]:
        match_query = _build_match_query(query)
        if not match_query:
            return []
        stmt = text(
            """
            SELECT c.id, c.name, c.description, c.category_id, c.price, c.link, c.is_active
            FROM courses_fts f
            JOIN courses c ON c.id = f.rowid
            WHERE courses_fts MATCH :q AND c.is_active = 1
            ORDER BY rank
            LIMIT :limit
            """
        )
        result = await self._session.execute(stmt, {"q": match_query, "limit": limit})
        return [
            Course(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                category_id=row["category_id"],
                price=Decimal(str(row["price"])),
                link=row["link"],
                is_active=bool(row["is_active"]),
                extra={},
            )
            for row in result.mappings().all()
        ]
