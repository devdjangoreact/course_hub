from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.domain.entities.parser_source import ParserSource


@dataclass(slots=True)
class ParsedCatalogItem:
    item_type: str
    fingerprint: str
    language_code: str
    payload: dict[str, Any]
    external_id: str | None = None
    source_url: str | None = None


@dataclass(slots=True)
class ParserResult:
    items: list[ParsedCatalogItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class CatalogParser(ABC):
    @abstractmethod
    async def parse(self, source: ParserSource) -> ParserResult: ...
