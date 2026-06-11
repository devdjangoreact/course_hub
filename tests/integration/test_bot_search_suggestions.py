from app.bot.keyboards.catalog import suggestions_keyboard
from app.domain.repositories.suggestion_search_repository import SearchSuggestion


def test_suggestions_keyboard_uses_selectable_course_callbacks() -> None:
    markup = suggestions_keyboard(
        [SearchSuggestion(type="course", id=1, title="Async FastAPI", subtitle=None, score=1.0)]
    )

    assert markup.inline_keyboard[0][0].text == "Async FastAPI"
    assert markup.inline_keyboard[0][0].callback_data == "course:1"


def test_suggestions_keyboard_uses_selectable_category_callbacks() -> None:
    markup = suggestions_keyboard(
        [SearchSuggestion(type="category", id=2, title="Programming", subtitle=None, score=0.7)]
    )

    assert markup.inline_keyboard[0][0].callback_data == "cat:2"
