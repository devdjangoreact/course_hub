DEFAULT_LANGUAGE = "ru"

_MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        "choose_language": "Выберите язык интерфейса:",
        "language_saved": "Язык сохранён.",
        "welcome": "Добро пожаловать в Course Hub! Выберите категорию или поиск.",
        "categories": "Категории",
        "search": "Поиск",
        "language": "Язык",
        "search_prompt": "Отправьте поисковый запрос:",
        "search_too_short": "Введите не менее 3 символов.",
        "search_rate_limited": "Слишком много запросов. Попробуйте немного позже.",
        "search_no_results": "Ничего не найдено. Попробуйте другой запрос.",
        "search_results": "Выберите результат:",
        "course_category": "Категория",
        "course_price": "Цена",
        "course_link": "Ссылка",
        "order": "Заказать",
        "back": "Назад",
        "menu": "Меню",
        "pay_here": "Оплатить здесь",
        "order_created": "Заказ создан",
        "course_not_found": "Курс не найден.",
        "payment_status": "Статус оплаты заказа",
        "order_payment_summary": (
            "<b>Заказ #{order_id}</b>\n\n"
            "Товар: {course_name}\n"
            "Категория: {category_name}\n"
            "Сервис оплаты: {payment_service}\n"
            "Сумма: {amount} {currency}\n\n"
            "Нажмите «Оплатить» ниже."
        ),
        "payment_provider_atlos": "atlos.io",
        "payment_provider_simulated": "Тестовая оплата",
        "pay_button": "Оплатить",
        "download_ready": "Ссылка для скачивания",
        "download_missing": "Ссылка для скачивания ещё не настроена. Обратитесь в поддержку.",
        "invite_line": "Доступ к каналу",
    },
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
        "order_payment_summary": (
            "<b>Замовлення #{order_id}</b>\n\n"
            "Товар: {course_name}\n"
            "Категорія: {category_name}\n"
            "Сервіс оплати: {payment_service}\n"
            "Сума: {amount} {currency}\n\n"
            "Натисніть «Оплатити» нижче."
        ),
        "payment_provider_atlos": "atlos.io",
        "payment_provider_simulated": "Тестова оплата",
        "pay_button": "Оплатити",
        "download_ready": "Посилання для скачування",
        "download_missing": "Посилання для скачування ще не налаштоване. Зверніться до підтримки.",
        "invite_line": "Доступ до каналу",
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
        "order_payment_summary": (
            "<b>Order #{order_id}</b>\n\n"
            "Product: {course_name}\n"
            "Category: {category_name}\n"
            "Payment service: {payment_service}\n"
            "Amount: {amount} {currency}\n\n"
            "Tap «Pay» below."
        ),
        "payment_provider_atlos": "atlos.io",
        "payment_provider_simulated": "Simulated payment",
        "pay_button": "Pay",
        "download_ready": "Download link",
        "download_missing": "Download link is not configured yet. Contact support.",
        "invite_line": "Channel access",
    },
}


def message(language_code: str, key: str) -> str:
    language_messages = _MESSAGES.get(language_code, _MESSAGES[DEFAULT_LANGUAGE])
    return language_messages.get(key, _MESSAGES[DEFAULT_LANGUAGE][key])
