# Enrich agent prompt (Flancki)

Ти обробляєш курси каталогу Flancki вручну (без `scripts/catalog_pipeline.py` і без `tools/catalog/enrich.py`).

Пошук і читання сторінок — лише через **Agent Reach** (не вигадуй URL і ціни).

## Старт (без підготовки)

Цей файл має пріоритет над skill-exploration (using-superpowers, Agent Reach `SKILL.md` / `references/*`, doctor, Todo, план). Команди вже нижче — не відкривай ті docs.

Почни з першої shell-команди в цьому ж ході відповіді:

1. PATH: `%USERPROFILE%\.agent-reach-venv\Scripts` + `C:\Program Files\nodejs` + `%APPDATA%\npm`
2. `Get-ChildItem data/catalog/categories/flancki_need_enrich/*.json | Sort-Object Name | Select-Object -First 10`
3. Для кожного файлу: візьми `title` → одразу Exa `#1` → fetch → route (free / old / flancki).
4. Не питай підтвердження між курсами. Не роби Todo/план окремим кроком.
5. Формат полів — лише з секції «Що записати»; не звіряйся з іншими JSON у каталозі.
6. Не читай README, `tools/catalog/*`, зразки з `flancki/` / `free/` / `flancki_old/`.

## Вхід

- Папка: `data/catalog/categories/flancki_need_enrich/`
- Візьми **перші 10** JSON-файлів (сортування за іменем файлу).
- Назва курсу: поле `title`. Ігноруй `download_link` / cloud.mail.ru як «офіційну» сторінку.
- Файли в цій папці **gitignored** — для списку використовуй shell (`dir` / `Get-ChildItem`), не Glob.

## Agent Reach — інструменти

PATH (Windows): `%USERPROFILE%\.agent-reach-venv\Scripts` + `C:\Program Files\nodejs` + `%APPDATA%\npm`.

На курс максимум **2 пошуки Exa** (не повторювати той самий запит):
1. `mcporter call exa.web_search_exa query="<title> офіційна сторінка" numResults=5`
2. Якщо дати немає на сторінці: `mcporter call exa.web_search_exa query="<title> дата старта" numResults=5`

Читання URL (один раз на кандидата): `curl -s "https://r.jina.ai/<URL>"` або `mcporter call exa.web_fetch_exa urls='["<URL>"]' maxCharacters=5000`  
YouTube (якщо URL з результатів): `yt-dlp --dump-json <URL>`

Не приймай як `original_url`: dump-сайти, форуми зі «скачати», cloud.mail.ru, telegram invite без лендінгу продажу.

## Куди класти (пріоритет зверху вниз)

1. **Безкоштовний** (`price` 0 / FREE / «бесплатно» / немає платної ціни) → одразу перенеси в `data/catalog/categories/free/`. Enrich не роби.
2. **Старий** (`course_date` < 2025-01-01) → перенеси в `data/catalog/categories/flancki_old/`. Повний enrich не роби (достатньо знати дату зі сторінки курсу).
3. **Платний і не старий** (`course_date` >= 2025-01-01) → повний enrich, потім у `data/catalog/categories/flancki/`.

Після переносу видали файл з `flancki_need_enrich`.

## Порядок на кожному файлі

1. Exa: `<title> офіційна сторінка` → обери кандидатів, fetch сторінку.
2. Зі сторінки дізнайся ціну. Якщо безкоштовний → крок 1 правил (free) і наступний файл.
3. `course_date` зі сторінки; якщо немає — один Exa: `<title> дата старта`. Не з Telegram і не з імені файлу. Якщо < 2025-01-01 → крок 2 правил (flancki_old) і наступний файл.
4. Інакше — збагачуй і клади в `flancki`.

## Що записати при повному enrich (лише платний → flancki)

1. `original_url` — офіційна сторінка продажу (школа, GetCourse, Skillbox, Udemy, лендінг автора). Не вигадуй. Не дамп-лінки.
2. `price` — число без валюти, рядок.
3. `course_date` у `other`: `{"course_date": "YYYY-MM-DD"}`.
4. `year` — рік з `course_date`.
5. `authors`, `tags`.
6. `short_description` — 1–3 речення.
7. `promo.text` + `full_description` — продажний Telegram HTML зі сторінки курсу, мовою `title`.

Приклад полів (платний → flancki):
`"original_url": "https://...", "price": "19990", "year": 2025, "other": {"course_date": "2025-03-15"}, "authors": ["..."], "tags": ["..."], "short_description": "...", "promo": {"text": "..."}, "full_description": "..."`

Якщо сторінку / ціну / дату не знайдено — не вигадуй; `original_url=null`, причина в `other`, файл лиши в `flancki_need_enrich`.

## Не робити

- Не запускати `catalog_pipeline` / enrich скрипти.
- Не брати більше ніж 10 файлів за прогін (якщо не сказали інакше).
- Не підставляти `download_link` як `original_url`.
- `category.slug` / `title` лишай `"flancki"` / `"Flancki"`.
- Не шукати через звичайний WebSearch, якщо Agent Reach доступний.
- Не робити повторні / зайві Exa-запити (не більше 2 на курс; не дублювати вже зроблений запит).
- Не читати Agent Reach / superpowers skills і references перед пошуком — достатньо команд у цьому файлі.
