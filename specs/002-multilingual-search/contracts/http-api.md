# HTTP/Admin Contract: Multilingual Catalog and Parser Jobs

These contracts describe the expected application-facing behavior. SQLAdmin may expose some of the
same models directly for administrators, but API behavior remains useful for tests and future UI.

## Languages

### `GET /api/languages`

Returns active supported languages.

Response:

```json
{
  "items": [
    {
      "code": "uk",
      "name": "Ukrainian",
      "native_name": "Українська",
      "is_default": true
    }
  ]
}
```

Rules:
- Only active languages are returned.
- Exactly one item has `is_default: true`.

## Localized Catalog

### `GET /api/categories?language=uk`

Returns categories localized to the requested language with fallback applied.

Response:

```json
{
  "items": [
    {
      "id": 1,
      "name": "Програмування",
      "language": "uk",
      "fallback_used": false
    }
  ]
}
```

### `GET /api/categories/{category_id}/courses?language=uk`

Returns active courses in a category localized to the requested language.

Response:

```json
{
  "items": [
    {
      "id": 10,
      "name": "Основи Python",
      "description": "Курс для старту з Python.",
      "price": "49.00",
      "link": "https://example.com/python",
      "language": "uk",
      "fallback_used": false
    }
  ]
}
```

Rules:
- Inactive/draft courses are never returned.
- Missing translations use default-language fallback.

## Search Suggestions

### `GET /api/search/suggestions?q=fas&language=uk&limit=5`

Returns localized selectable suggestions for queries of at least 3 meaningful characters.

Response:

```json
{
  "items": [
    {
      "type": "course",
      "id": 2,
      "title": "Async FastAPI",
      "subtitle": "Build async APIs with FastAPI.",
      "score": 0.92
    }
  ]
}
```

Validation:
- `q` shorter than 3 meaningful characters returns a validation error.
- `limit` is bounded by the application maximum.
- Results include only active public catalog items.

## Parser Sources

### `POST /api/admin/parser-sources`

Creates an allowed parser source.

Request:

```json
{
  "name": "Example Catalog",
  "source_type": "html",
  "url": "https://example.com/courses",
  "is_active": true,
  "extra": {}
}
```

Response:

```json
{
  "id": 1,
  "name": "Example Catalog",
  "source_type": "html",
  "url": "https://example.com/courses",
  "is_active": true
}
```

Rules:
- Admin authentication is required.
- Secrets must not be accepted in plain request fields intended for display/logging.

### `POST /api/admin/parser-sources/{source_id}/jobs`

Starts a parser job for an active source.

Response:

```json
{
  "id": 100,
  "source_id": 1,
  "status": "pending",
  "imported_count": 0,
  "skipped_count": 0
}
```

Rules:
- Inactive sources cannot start jobs.
- Starting the same source multiple times creates separate job records but does not create duplicate
  public catalog items.

### `GET /api/admin/parser-jobs/{job_id}`

Returns parser job status and safe report details.

Response:

```json
{
  "id": 100,
  "source_id": 1,
  "status": "completed",
  "imported_count": 8,
  "skipped_count": 2,
  "error_summary": null
}
```

### `POST /api/admin/imported-items/{item_id}/approve`

Approves a draft/matched imported item into the reviewable catalog.

Rules:
- Approval does not auto-publish an active course unless the admin explicitly activates it.
- Duplicate matches are preserved for admin review instead of silently overwriting public catalog
  content.
