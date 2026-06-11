from abc import ABC, abstractmethod

from app.domain.entities.supported_language import SupportedLanguage


class LanguageRepository(ABC):
    @abstractmethod
    async def list_active(self) -> list[SupportedLanguage]: ...

    @abstractmethod
    async def get(self, code: str) -> SupportedLanguage | None: ...

    @abstractmethod
    async def get_default(self) -> SupportedLanguage: ...

    @abstractmethod
    async def add(self, language: SupportedLanguage) -> SupportedLanguage: ...
