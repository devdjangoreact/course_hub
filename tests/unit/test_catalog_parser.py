import pytest

from app.domain.entities.parser_source import ParserSource
from app.infrastructure.parsers.catalog_parser import HttpCatalogParser


@pytest.mark.asyncio
async def test_inactive_source_returns_safe_error() -> None:
    parser = HttpCatalogParser()

    result = await parser.parse(
        ParserSource(
            id=1,
            name="Example",
            source_type="html",
            url="https://example.com",
            is_active=False,
        )
    )

    assert result.errors == ["Source is inactive"]
