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
        "payment_email_prompt": "Введіть email для оплати через lava.top:",
        "payment_email_invalid": "Некоректний email. Спробуйте ще раз.",
        "payment_email_confirm": "Збережений email: <code>{email}</code>\n\nВикористати його для оплати?",
        "payment_email_use": "Так, використати",
        "payment_email_change": "Інший email",
        "order_payment_summary": (
            "<b>Замовлення #{order_id}</b>\n\n"
            "Товар: {course_name}\n"
            "Категорія: {category_name}\n"
            "Сервіс оплати: {payment_service}\n"
            "Сума: {amount} {currency}\n\n"
            "Натисніть «Оплатити» нижче."
        ),
        "payment_provider_lava": "lava.top",
        "payment_provider_simulated": "Тестова оплата",
        "pay_button": "Оплатити",
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
        "payment_email_prompt": "Enter your email for lava.top checkout:",
        "payment_email_invalid": "Invalid email. Please try again.",
        "payment_email_confirm": "Saved email: <code>{email}</code>\n\nUse it for checkout?",
        "payment_email_use": "Yes, use this email",
        "payment_email_change": "Use another email",
        "order_payment_summary": (
            "<b>Order #{order_id}</b>\n\n"
            "Product: {course_name}\n"
            "Category: {category_name}\n"
            "Payment service: {payment_service}\n"
            "Amount: {amount} {currency}\n\n"
            "Tap «Pay» below."
        ),
        "payment_provider_lava": "lava.top",
        "payment_provider_simulated": "Simulated payment",
        "pay_button": "Pay",
    },
}


def message(language_code: str, key: str) -> str:
    language_messages = _MESSAGES.get(language_code, _MESSAGES[DEFAULT_LANGUAGE])
    return language_messages.get(key, _MESSAGES[DEFAULT_LANGUAGE][key])
