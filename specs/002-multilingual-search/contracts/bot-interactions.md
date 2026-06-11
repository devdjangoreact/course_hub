# Telegram Bot Interaction Contract

## Language Selection

### New user flow

1. User sends `/start`.
2. If no valid saved language exists, bot sends a language selection message.
3. User taps a language button.
4. Bot saves the choice and shows the localized main menu.

Expected buttons:

```text
Українська
English
```

Rules:
- Language buttons use stable callback data containing the language code.
- Unsupported/stale saved language triggers language selection again.
- User can change language later from the main menu.

### Returning user flow

1. User sends `/start`.
2. Bot loads saved language.
3. Bot shows localized main menu without asking again.

## Main Menu

Localized menu entries:

```text
Categories
Search
Language
```

Rules:
- Labels are displayed in the user's selected language.
- The menu remains usable if a translation key is missing by falling back to the default language.

## Localized Category Browsing

1. User taps categories.
2. Bot shows localized category names.
3. User taps a category.
4. Bot shows active localized courses for that category.

Rules:
- Category/course translation fallback is applied before rendering.
- Inactive/draft courses are hidden.
- Empty category states are localized.

## Course Display

Course detail messages include:

```text
<Course name>
Category: <Category name>
Price: <price currency>

<Description>
```

Buttons:

```text
Order
Back
Search
```

Rules:
- Long descriptions are shortened or split to stay readable within Telegram limits.
- Links remain visible or actionable.
- Price formatting remains stable and language-safe.

## Search and Suggestions

1. User taps search.
2. Bot asks for a query in the selected language.
3. If query has fewer than 3 meaningful characters, bot asks for a longer query.
4. If query has 3 or more meaningful characters, bot returns selectable suggestions.

Suggestion button examples:

```text
Course: Async FastAPI
Category: Programming
```

Rules:
- Suggestions use inline buttons with stable callback IDs.
- Results are localized with fallback.
- Existing 5-per-minute user search limit applies.
- No-results and throttled messages are localized.

## Orders and Payments

Rules:
- Order creation and payment status messages use the selected language.
- Course identity, price, and payment status behavior stay unchanged.
- Payment confirmation remains idempotent.
- User language changes affect future order/payment messages.
