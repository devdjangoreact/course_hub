import pytest

from app.application.services.localization_service import LocalizationService
from app.domain.entities.supported_language import SupportedLanguage
from app.domain.repositories.language_repository import LanguageRepository


class FakeLanguageRepository(LanguageRepository):
    def __init__(self) -> None:
        self._languages = {
            "uk": SupportedLanguage(
                code="uk",
                name="Ukrainian",
                native_name="Українська",
                is_default=True,
            ),
            "en": SupportedLanguage(code="en", name="English", native_name="English"),
        }

    async def list_active(self) -> list[SupportedLanguage]:
        return list(self._languages.values())

    async def get(self, code: str) -> SupportedLanguage | None:
        return self._languages.get(code)

    async def get_default(self) -> SupportedLanguage:
        return self._languages["uk"]

    async def add(self, language: SupportedLanguage) -> SupportedLanguage:
        self._languages[language.code] = language
        return language


@pytest.mark.asyncio
async def test_resolve_supported_language() -> None:
    service = LocalizationService(FakeLanguageRepository())

    assert await service.resolve_language("en") == "en"


@pytest.mark.asyncio
async def test_resolve_language_falls_back_to_default() -> None:
    service = LocalizationService(FakeLanguageRepository())

    assert await service.resolve_language("de") == "uk"
    assert await service.resolve_language(None) == "uk"
