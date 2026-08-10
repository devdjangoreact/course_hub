"""Quality gate: checklist, LLM judge, extract_metadata_with_quality."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from .llm import LLM_BACKEND, llm_text
from .taxonomy import load_taxonomy, taxonomy_prompt_block

ENRICH_MAX_RETRIES = 1  # one retry after failed checklist/judge
JUDGE_MIN_SCORE = 7

# Adapted from scripts/enrich_agent_prompt.md for SearXNG-scraped sources.
SYSTEM_PROMPT = """You enrich an online-course catalog record from SearXNG search hits and scraped page text.

Respond with STRICT JSON only (no markdown, no commentary) — ONLY the enrich fields below:
{
  "original_url": string|null,
  "price": string|null,
  "is_free": boolean,
  "course_date": string|null,
  "year": integer|null,
  "authors": [string],
  "category": string|null,
  "subcategory": string|null,
  "tags": [string],
  "short_description": string,
  "promo_text": string,
  "full_description": string,
  "telegram_post": string,
  "skip_reason": string|null
}

=== ENRICH (you must fill these when sources allow) ===
- original_url
- price
- is_free
- course_date  (maps to other.course_date)
- year
- authors
- category     (topic category from taxonomy; NOT catalog folder "flancki")
- subcategory  (from taxonomy under that category)
- tags
- short_description
- promo_text  (maps to promo.text)
- full_description
- telegram_post
- skip_reason  (only if almost nothing useful was found)

=== DO NOT TOUCH (keep as in catalog; never rewrite/invent) ===
- slug
- category object in catalog JSON (slug/title flancki) — separate from enrich "category"
- title
- download_link
- links  (pipeline may append original_url itself)
- telegram  (channel_id, discussion_group_id, invite_link, message ids)
- source  (adapter, external_id, raw_refs)
- promo.media

=== FILLED BY PIPELINE (not you) ===
- enrich_sources  (URLs of pages used for enrich)
- taxonomy file updates when you propose a new category/subcategory/tag

Rules:
- category / subcategory: prefer exact names from the Allowed taxonomy in the user message. Pick the single best category + subcategory. If nothing fits, invent a short clear new name — the pipeline will append it to the taxonomy.
- tags: 4-8 hashtags. Each item MUST start with # and contain no spaces (CamelCase or underscores), e.g. "#Трейдинг", "#ПсихологияТрейдера", "#trading". Prefer taxonomy names converted to hashtags. Also paste the same hashtags as a final line in promo_text, full_description, and telegram_post (space-separated).
- Prefer official sales/marketing pages (school storefront, author landing, GetCourse, Skillbox, Udemy, etc.) for original_url.
- original_url = official page only. If none found: null. Do NOT put dump/leak/reseller/cloud/telegram-invite URLs into original_url.
- You MAY extract facts (date, authors, descriptions) from unofficial pages when that is all that is available. Prefer official sources when both exist.
- NEVER invent URLs or dates. Only use facts present in the sources.
- Ignore download_link / cloud mirrors from the catalog dump as original_url.
- price: ALWAYS "5" for paid catalog courses (our sell price in USDT). Never use rubles/RUB/₽ or the author's storefront price. Use "0" only when the course is clearly free.
- is_free: true if sources say free / FREE / «бесплатно»; otherwise false (and price must be "5").
- In all sales copy (promo_text, full_description, telegram_post): quote price only as <b>5 USDT</b>. Never mention rubles or other currencies.
- course_date: "YYYY-MM-DD" when known. null if unknown.
- year: year from course_date when available, else null.
- Always do full enrich when sources allow: category, subcategory, tags, short_description, promo_text, full_description, telegram_post, authors.
- short_description: 3-5 sentences, language close to the course title.
- promo_text + full_description: long Telegram HTML sales copy, same language as the title. Structure: 5-6 paragraphs separated by blank lines (\\n\\n). Total length 25-30 sentences (who the course is for, author/context, program modules, benefits/outcomes, practice/format, offer + buy CTA). End with CTA (e.g. «Купить за 5 USDT») then a final line of hashtags.
- telegram_post: long sales-oriented Telegram HTML post (title, hook, detailed benefits, modules, who it fits, price 5 USDT, strong buy CTA, hashtag line). Use <b>, <i>, newlines. Do not invent URLs; include original_url only if set. Aim for depth close to full_description (not a short teaser).
- If almost nothing useful can be extracted: skip_reason explaining why; leave enrich fields empty/null.

Example of a correctly filled catalog course (annotated; your reply is ONLY the ENRICH schema above):
{
  "slug": "2026-01-05_2141_01",                          // DO NOT TOUCH
  "category": {"slug": "flancki", "title": "Flancki"},    // DO NOT TOUCH
  "title": "Виртуозный трейдинг с Доктором Богатовым (2017)",  // DO NOT TOUCH
  "short_description": "Практический курс по трейдингу от Доктора Богатова (2017): стратегии входа и выхода, психология рынка и разбор реальных сделок. Подходит новичкам и тем, кто хочет системный подход без хаоса сигналов.",  // ENRICH
  "price": "5",                                           // ENRICH (always 5 USDT when paid)
  "is_free": false,                                       // ENRICH
  "promo": {
    "text": "<b>Виртуозный трейдинг с Доктором Богатовым (2017)</b>\\n\\nКурс раскрывает, как читать рынок и принимать решения без хаоса. Вы пройдете логику входа и выхода, управление риском и типичные ошибки новичков. Материал подходит тем, кто хочет системный подход, а не набор разрозненных сигналов. Автор объясняет, почему импульсивные сделки разрушают депозит и как заменить их правилами.\\n\\nВо второй части — психология трейдера: дисциплина, работа с эмоциями и правила, которые помогают не сливать депозит. Есть практические блоки и ориентиры, как применять идеи на реальном графике. Вы получите понятную рамку для самостоятельной торговли. Отдельно разбираются сценарии бокового рынка и тренда.\\n\\nДальше — структура дня трейдера, чек-листы перед входом и фиксация результатов. Вы научитесь вести простой журнал сделок и видеть повторяющиеся ошибки. Курс показывает, как строить план без перегрузки индикаторами. Это база для тех, кто устал от хаотичной торговли.\\n\\nПрактические примеры помогают связать теорию с графиком. Вы увидите, как выглядит рабочий сетап и когда лучше пропустить сделку. Материал рассчитан на самостоятельную проработку в удобном темпе. Даже короткие сессии дают прогресс, если следовать правилам.\\n\\nВ финале — сборка своей мини-системы: фильтры входа, риск на сделку и критерии выхода. Вы закрепите привычку следовать плану, а не эмоциям. Доступ к курсу в каталоге — <b>5 USDT</b>. Купите курс сейчас и начните собирать торговую систему уже сегодня.\\n\\n#Трейдинг #trading #ПсихологияТрейдера #РискМенеджмент",  // ENRICH via promo_text
    "media": []                                           // DO NOT TOUCH
  },
  "full_description": "<b>Виртуозный трейдинг с Доктором Богатовым (2017)</b>\\n\\nКурс раскрывает, как читать рынок и принимать решения без хаоса. Вы пройдете логику входа и выхода, управление риском и типичные ошибки новичков. Материал подходит тем, кто хочет системный подход, а не набор разрозненных сигналов. Автор объясняет, почему импульсивные сделки разрушают депозит и как заменить их правилами.\\n\\nВо второй части — психология трейдера: дисциплина, работа с эмоциями и правила, которые помогают не сливать депозит. Есть практические блоки и ориентиры, как применять идеи на реальном графике. Вы получите понятную рамку для самостоятельной торговли. Отдельно разбираются сценарии бокового рынка и тренда.\\n\\nДальше — структура дня трейдера, чек-листы перед входом и фиксация результатов. Вы научитесь вести простой журнал сделок и видеть повторяющиеся ошибки. Курс показывает, как строить план без перегрузки индикаторами. Это база для тех, кто устал от хаотичной торговли.\\n\\nПрактические примеры помогают связать теорию с графиком. Вы увидите, как выглядит рабочий сетап и когда лучше пропустить сделку. Материал рассчитан на самостоятельную проработку в удобном темпе. Даже короткие сессии дают прогресс, если следовать правилам.\\n\\nВ финале — сборка своей мини-системы: фильтры входа, риск на сделку и критерии выхода. Вы закрепите привычку следовать плану, а не эмоциям. Доступ к курсу в каталоге — <b>5 USDT</b>. Купите курс сейчас и начните собирать торговую систему уже сегодня.\\n\\n#Трейдинг #trading #ПсихологияТрейдера #РискМенеджмент",  // ENRICH
  "telegram_post": "<b>📈 Виртуозный трейдинг</b>\\n\\nКурс Доктора Богатова (2017): стратегии, психология и практика без хаоса сигналов. Разберете вход/выход, риск и типичные ошибки.\\n\\n✅ системные правила вместо импульса\\n✅ психология и дисциплина\\n✅ практика на графике и журнал сделок\\n\\n💰 Цена: <b>5 USDT</b>\\n\\n👉 Купить курс за 5 USDT и начать обучение сегодня.\\n\\n#Трейдинг #trading #ПсихологияТрейдера #РискМенеджмент",  // ENRICH
  "download_link": "https://cloud.mail.ru/public/2gfX/5fFBPBfU7",  // DO NOT TOUCH
  "links": ["https://cloud.mail.ru/public/2gfX/5fFBPBfU7"],        // DO NOT TOUCH (pipeline may append)
  "enrich_sources": [                                     // PIPELINE
    "https://www.youtube.com/@drbogatov",
    "https://sharewood.tech/example-bogatov-trading"
  ],
  "authors": ["Доктор Богатов"],                          // ENRICH
  "topic_category": "Трейдинг",                           // ENRICH via category
  "subcategory": "Психология трейдера",                   // ENRICH
  "year": 2017,                                           // ENRICH
  "tags": ["#Трейдинг", "#trading", "#ПсихологияТрейдера", "#РискМенеджмент"], // ENRICH
  "other": [{"course_date": "2017-01-01"}],               // ENRICH via course_date
  "original_url": null,                                   // ENRICH (null if no official page)
  "telegram": {                                           // DO NOT TOUCH
    "channel_id": null,
    "discussion_group_id": null,
    "invite_link": null,
    "promo_message_ids": [],
    "full_message_ids": []
  },
  "source": {                                             // DO NOT TOUCH
    "adapter": "telegram_flancki_pyrogram",
    "external_id": "-1001343804259:2141:01",
    "raw_refs": [{"post_id": 2141, "chat_id": -1001343804259, "course_index": 1}]
  }
}
"""

JUDGE_SYSTEM_PROMPT = """You judge an enriched course JSON against the scraped sources.

Respond with STRICT JSON only:
{"score": integer 1-10, "pass": boolean, "reasons": [string]}

Scoring:
- 9-10: factual; promo/full ~5-6 paragraphs / 25-30 sentences; hashtag tags; clear buy CTA; price shown as 5 USDT (not RUB); no invented URL/date
- 7-8: usable; minor gaps ok (e.g. original_url null if truly missing)
- 1-6: weak/incomplete/hallucinated/copy of title only / wrong taxonomy / rubles in copy / no CTA / too short / tags without #
pass = score >= 7.
reasons: short concrete fail notes (empty list if pass).
"""


def clean_json(text: str) -> dict:
    text = re.sub(r"^```json|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def parse_course_date(raw: Any) -> date | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_user_prompt(
    course_title: str,
    pages: list[dict],
    download_link: str = "",
    feedback: str = "",
) -> str:
    sources_block = "\n\n".join(
        f"URL: {p['url']}\n"
        f"OG title: {p.get('og_title', '')}\n"
        f"OG description: {p.get('og_description', '')}\n"
        f"JSON-LD date: {p.get('json_ld_date', '')}\n"
        f"JSON-LD year: {p.get('json_ld_year', '')}\n"
        f"Body excerpt: {p.get('body_text', '')[:1500]}"
        for p in pages
        if p
    )
    parts = [
        f"Course title: {course_title}",
        f"Existing dump/download link (NOT the sales page): {download_link}",
        "",
        taxonomy_prompt_block(load_taxonomy()),
        "",
        f"Sources from SearXNG + fetch:\n{sources_block}",
    ]
    if feedback.strip():
        parts.extend(
            [
                "",
                "Previous enrich was rejected. Fix ALL issues below and return a full corrected JSON:",
                feedback.strip(),
            ]
        )
    return "\n".join(parts)


def extract_metadata(
    course_title: str,
    pages: list[dict],
    download_link: str = "",
    feedback: str = "",
) -> dict:
    return clean_json(
        llm_text(
            SYSTEM_PROMPT,
            _build_user_prompt(course_title, pages, download_link, feedback=feedback),
        )
    )


_RUB_RE = re.compile(r"(?:₽|\bруб(?:л(?:ей|я|ь)?)?\b\.?|\bRUB\b)", re.IGNORECASE)
_RUB_AMOUNT_RE = re.compile(
    r"\d[\d\s]*(?:[.,]\d+)?\s*(?:₽|\bруб(?:л(?:ей|я|ь)?)?\b\.?|\bRUB\b)",
    re.IGNORECASE,
)
_CTA_RE = re.compile(
    r"(?:купит[ьи]|забрать|оформит[ьи]|купить курс|забрать курс)",
    re.IGNORECASE,
)


def _nonempty(val: Any, min_len: int = 1) -> bool:
    return isinstance(val, str) and len(val.strip()) >= min_len


def _sales_blob(extracted: dict[str, Any]) -> str:
    parts = [
        extracted.get("promo_text"),
        extracted.get("full_description"),
        extracted.get("telegram_post"),
    ]
    return "\n".join(p for p in parts if isinstance(p, str))


def normalize_hashtag(tag: str) -> str:
    """Force #TagWithNoSpaces (spaces removed)."""
    text = str(tag).strip()
    if text.startswith("#"):
        text = text[1:]
    body = re.sub(r"[\s/|,;]+", "", text)
    return f"#{body}" if body else ""


def normalize_sell_price(extracted: dict[str, Any]) -> None:
    """Force catalog sell price: 0 if free, else 5 USDT."""
    if extracted.get("is_free") is True:
        extracted["price"] = "0"
    else:
        extracted["is_free"] = False
        extracted["price"] = "5"


def scrub_rubles_from_sales(extracted: dict[str, Any]) -> None:
    """Titles often contain «руб» — strip currency from sales copy before gate."""
    for key in ("promo_text", "full_description", "telegram_post", "short_description"):
        text = extracted.get(key)
        if not isinstance(text, str) or not text.strip():
            continue
        cleaned = _RUB_AMOUNT_RE.sub("доход", text)
        cleaned = _RUB_RE.sub("", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        extracted[key] = cleaned


def normalize_tags(extracted: dict[str, Any]) -> None:
    raw = extracted.get("tags") if isinstance(extracted.get("tags"), list) else []
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        tag = normalize_hashtag(item)
        key = tag.casefold()
        if tag and key not in seen:
            seen.add(key)
            tags.append(tag)
    extracted["tags"] = tags
    if not tags:
        return
    line = " ".join(tags)
    for key in ("promo_text", "full_description", "telegram_post"):
        text = extracted.get(key)
        if not isinstance(text, str) or not text.strip():
            continue
        if all(t.casefold() in text.casefold() for t in tags):
            continue
        extracted[key] = text.rstrip() + "\n\n" + line


def checklist(extracted: dict[str, Any], course_title: str) -> tuple[bool, list[str]]:
    """Deterministic quality gate. Returns (ok, fail_reasons)."""
    fails: list[str] = []
    title = (course_title or "").strip()

    if not _nonempty(extracted.get("short_description"), 40):
        fails.append("short_description missing or too short (<40 chars)")
    elif (
        _nonempty(extracted.get("short_description"))
        and extracted["short_description"].strip() == title
    ):
        fails.append("short_description is a copy of the title")

    if not _nonempty(extracted.get("telegram_post"), 200):
        fails.append("telegram_post missing or too short (<200 chars)")
    elif (
        _nonempty(extracted.get("telegram_post"))
        and title
        and title in extracted["telegram_post"]
        and len(extracted["telegram_post"].strip()) < len(title) + 40
    ):
        fails.append("telegram_post is too close to the title only")

    promo = extracted.get("promo_text") or extracted.get("full_description")
    if not _nonempty(promo, 1200):
        fails.append(
            "promo_text/full_description missing or too short "
            "(<1200 chars; want ~5-6 paragraphs / 25-30 sentences)"
        )
    elif isinstance(promo, str) and promo.count("\n\n") < 4:
        fails.append("promo_text/full_description need 5+ paragraphs (4 blank-line separators)")

    if not _nonempty(extracted.get("category")):
        fails.append("category (topic) missing")

    tags = extracted.get("tags") if isinstance(extracted.get("tags"), list) else []
    tags = [t for t in tags if isinstance(t, str) and t.strip()]
    if len(tags) < 4:
        fails.append("tags: need at least 4 hashtags")
    if len(tags) > 8:
        fails.append("tags: too many (>8), keep 4-8")
    if any(not t.startswith("#") or " " in t for t in tags):
        fails.append("tags must be hashtags starting with # and without spaces")
    sales = _sales_blob(extracted)
    if tags and not all(t in sales for t in tags):
        fails.append("sales copy must include the hashtag tags line")

    price = extracted.get("price")
    is_free = extracted.get("is_free") is True
    if _RUB_RE.search(sales):
        fails.append("sales copy must not use rubles/RUB/₽ — use 5 USDT")
    if is_free:
        if price is not None:
            text = str(price).strip().lower().replace(",", ".")
            try:
                if (
                    text not in {"0", "0.0", "0.00", "free", "бесплатно", "бесплатный"}
                    and float(text) != 0.0
                ):
                    fails.append("is_free=true but price is non-zero")
            except ValueError:
                fails.append("is_free=true but price is not a free-like value")
    else:
        if str(price).strip() != "5":
            fails.append('paid course price must be "5" (USDT)')
        if "5 USDT" not in sales and "5 usdt" not in sales.lower():
            fails.append("sales copy must mention 5 USDT")
        if not _CTA_RE.search(sales):
            fails.append("sales copy needs a buy CTA (купить / забрать / оформить)")

    raw_url = extracted.get("original_url")
    if isinstance(raw_url, str) and raw_url.strip():
        url = raw_url.strip().lower()
        if not url.startswith(("http://", "https://")):
            fails.append("original_url must be http(s) or null")
        banned = ("cloud.mail.ru", "t.me/", "telegram.me", "disk.yandex", "drive.google.com")
        if any(b in url for b in banned):
            fails.append("original_url looks like dump/cloud/telegram, use null instead")

    course_date = extracted.get("course_date")
    if course_date is not None and course_date != "":
        if parse_course_date(course_date) is None:
            fails.append("course_date must be YYYY-MM-DD or null")

    year = extracted.get("year")
    if year is not None and not isinstance(year, int):
        fails.append("year must be integer or null")
    parsed = parse_course_date(course_date) if course_date else None
    if parsed and isinstance(year, int) and year != parsed.year:
        fails.append("year does not match course_date")

    return (len(fails) == 0, fails)


def needs_judge(extracted: dict[str, Any]) -> bool:
    """Run LLM judge only for doubtful but checklist-passing results."""
    url = extracted.get("original_url")
    if not (isinstance(url, str) and url.strip()):
        return True
    tags = extracted.get("tags") if isinstance(extracted.get("tags"), list) else []
    if len([t for t in tags if isinstance(t, str) and t.strip()]) < 3:
        return True
    if not _nonempty(extracted.get("telegram_post"), 200):
        return True
    if not _nonempty(extracted.get("subcategory")):
        return True
    authors = extracted.get("authors") if isinstance(extracted.get("authors"), list) else []
    if not any(isinstance(a, str) and a.strip() for a in authors):
        return True
    return False


def judge_enrichment(
    course_title: str, pages: list[dict], extracted: dict[str, Any]
) -> dict[str, Any]:
    sources = "\n".join(f"- {p.get('url')} | {p.get('og_title', '')[:80]}" for p in pages if p)
    user = (
        f"Course title: {course_title}\n"
        f"Sources:\n{sources}\n\n"
        f"Enrich JSON:\n{json.dumps(extracted, ensure_ascii=False)}"
    )
    try:
        result = clean_json(llm_text(JUDGE_SYSTEM_PROMPT, user, max_tokens=1024))
    except (json.JSONDecodeError, TypeError, KeyError, IndexError) as exc:
        print(f"  judge parse fail: {exc}")
        return {"score": 0, "pass": False, "reasons": ["judge_response_invalid"]}
    score = result.get("score")
    try:
        score_i = int(score)
    except (TypeError, ValueError):
        score_i = 0
    reasons = result.get("reasons") if isinstance(result.get("reasons"), list) else []
    reasons = [str(r) for r in reasons if r]
    passed = bool(result.get("pass")) if "pass" in result else score_i >= JUDGE_MIN_SCORE
    if score_i < JUDGE_MIN_SCORE:
        passed = False
    return {"score": score_i, "pass": passed, "reasons": reasons}


def extract_metadata_with_quality(
    course_title: str,
    pages: list[dict],
    download_link: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enrich + hybrid C gate. Returns (extracted, quality_meta)."""
    feedback = ""
    extracted: dict[str, Any] = {}
    quality: dict[str, Any] = {"checklist_ok": False, "judge": None, "attempts": 0}

    for attempt in range(ENRICH_MAX_RETRIES + 1):
        quality["attempts"] = attempt + 1
        print(f"  llm ({LLM_BACKEND}) attempt {attempt + 1}…")
        try:
            extracted = extract_metadata(
                course_title, pages, download_link, feedback=feedback
            )
        except Exception as exc:  # noqa: BLE001 — keep batch alive on LLM outages
            reason = f"llm_error: {type(exc).__name__}: {exc}"
            print(f"  {reason}")
            extracted = {"skip_reason": reason}
            quality["checklist_ok"] = False
            quality["checklist_fails"] = [reason]
            break
        normalize_sell_price(extracted)
        scrub_rubles_from_sales(extracted)
        normalize_tags(extracted)

        ok, fails = checklist(extracted, course_title)
        quality["checklist_ok"] = ok
        quality["checklist_fails"] = fails
        if not ok:
            print(f"  checklist FAIL: {'; '.join(fails)}")
            if attempt < ENRICH_MAX_RETRIES:
                feedback = "Checklist failures:\n- " + "\n- ".join(fails)
                continue
            break

        print("  checklist OK")
        if not needs_judge(extracted):
            quality["judge"] = {"skipped": True, "pass": True, "score": 10, "reasons": []}
            print("  judge skipped (not doubtful)")
            break

        print("  judge…")
        judgment = judge_enrichment(course_title, pages, extracted)
        quality["judge"] = judgment
        print(f"  judge score={judgment['score']} pass={judgment['pass']}")
        if judgment["pass"]:
            break
        if attempt < ENRICH_MAX_RETRIES:
            reasons = judgment["reasons"] or [f"score {judgment['score']} < {JUDGE_MIN_SCORE}"]
            feedback = "Judge rejected enrich (score "
            feedback += f"{judgment['score']}/{JUDGE_MIN_SCORE}):\n- " + "\n- ".join(reasons)
            continue
        break

    return extracted, quality
