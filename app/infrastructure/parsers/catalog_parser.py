from app.domain.entities.parser_source import ParserSource
from app.domain.repositories.catalog_parser import CatalogParser, ParserResult


class HttpCatalogParser(CatalogParser):
    async def parse(self, source: ParserSource) -> ParserResult:
        if not source.is_active:
            return ParserResult(errors=["Source is inactive"])
        return ParserResult()
