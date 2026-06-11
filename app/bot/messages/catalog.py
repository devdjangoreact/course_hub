DEFAULT_LANGUAGE = "uk"

_MESSAGES: dict[str, dict[str, str]] = {
    "uk": {
        "choose_language": "Оберіть мову інтерфейсу:",
        "language_saved": "Мову збережено.",
        "welcome": "Вітаємо в Course Hub! Оберіть категорію або пошук.",
        "categories": "Категорії",
        "search": "Пошук",
        "language": "Мова",
        "search_prompt": "Надішліть пошуковий запит:",
        "search_too_short": "Введіть щонайменше 3 символи.",
        "search_rate_limited": "Забагато пошуків. Спробуйте трохи пізніше.",
        "search_no_results": "Нічого не знайдено. Спробуйте інший запит.",
        "search_results": "Оберіть результат:",
        "course_category": "Категорія",
        "course_price": "Ціна",
        "course_link": "Посилання",
        "order": "Замовити",
        "back": "Назад",
        "menu": "Меню",
        "pay_here": "Оплатити тут",
        "order_created": "Замовлення створено",
        "course_not_found": "Курс не знайдено.",
        "payment_status": "Статус оплати замовлення",
    },
    "en": {
        "choose_language": "Choose interface language:",
        "language_saved": "Language saved.",
        "welcome": "Welcome to Course Hub! Browse courses by category or search.",
        "categories": "Categories",
        "search": "Search",
        "language": "Language",
        "search_prompt": "Send a search term:",
        "search_too_short": "Enter at least 3 characters.",
        "search_rate_limited": "Too many searches. Please try again shortly.",
        "search_no_results": "No results. Try another term.",
        "search_results": "Choose a result:",
        "course_category": "Category",
        "course_price": "Price",
        "course_link": "Link",
        "order": "Order",
        "back": "Back",
        "menu": "Menu",
        "pay_here": "Pay here",
        "order_created": "Order created",
        "course_not_found": "Course not found.",
        "payment_status": "Order payment status",
    },
}


def message(language_code: str, key: str) -> str:
    language_messages = _MESSAGES.get(language_code, _MESSAGES[DEFAULT_LANGUAGE])
    return language_messages.get(key, _MESSAGES[DEFAULT_LANGUAGE][key])
