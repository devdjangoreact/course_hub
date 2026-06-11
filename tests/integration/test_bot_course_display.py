from app.bot.keyboards.catalog import course_detail_keyboard


def test_course_detail_keyboard_uses_localized_actions() -> None:
    markup = course_detail_keyboard(1, "uk")

    assert markup.inline_keyboard[0][0].text == "Замовити"
    assert markup.inline_keyboard[1][0].text == "Меню"
