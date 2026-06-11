from app.domain.entities.supported_language import SupportedLanguage
from app.domain.repositories.language_repository import LanguageRepository


class LocalizationService:
    def __init__(self, languages: LanguageRepository) -> None:
        self._languages = languages

    async def list_active_languages(self) -> list[SupportedLanguage]:
        return await self._languages.list_active()

    async def is_supported(self, language_code: str | None) -> bool:
        if not language_code:
            return False
        language = await self._languages.get(language_code)
        return language is not None and language.is_active

    async def resolve_language(self, language_code: str | None) -> str:
        if await self.is_supported(language_code):
            return str(language_code)
        default = await self._languages.get_default()
        return default.code
