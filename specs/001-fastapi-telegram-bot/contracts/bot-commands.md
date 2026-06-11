# Contract: Telegram Bot (aiogram)

Long-polling bot. Inline keyboards drive navigation; FSM handles multi-step flows (search, order).

## Commands

- `/start` → greet the user (upsert `BotUser`) and show the main menu.
- `/help` → short usage text and the main menu.

## Main menu (inline keyboard)

- `📚 Categories` → show the category list.
- `🔎 Search` → enter search state, prompt for a query.

## Category flow

1. `Categories` → list categories as buttons.
2. Selecting a category → list its active courses (name + price), each as a button.
3. Selecting a course → show full details (name, description, price, link) + `🛒 Order` button.
4. Empty category → "no courses yet" message + back button.

## Search flow (FSM)

1. `Search` → state `awaiting_query`, prompt "Send a search term".
2. User text → run full-text search over active courses; show ranked results as course buttons.
3. No results → "no results, try another term".
4. Empty/whitespace input → ask again for a valid term.
5. Rate limit: at most 5 searches per user per 60s; the 6th within the window → friendly
   "please slow down, try again in a moment" message (no DB query performed).

## Order flow (FSM)

1. `Order` on a course → create a `pending` order (snapshot price), reply with payment
   instructions/link.
2. On payment confirmation (via webhook) → bot notifies the user that the order is `paid`.
3. On failure/cancel → notify the user; offer retry.

## Behavior rules

- Only active courses appear in menus and search results.
- Long descriptions are truncated in lists and shown fully on the detail view.
- Network/DB errors are caught at the handler boundary and surfaced as a friendly message; full
  error context is logged (no secrets).
