# Parser Source Contract

Parser adapters fetch external resources and normalize them into draft catalog items. They do not
publish public categories/courses directly.

## Input

Parser job receives:

```json
{
  "job_id": 100,
  "source": {
    "id": 1,
    "name": "Example Catalog",
    "source_type": "html",
    "url": "https://example.com/courses",
    "extra": {}
  }
}
```

Rules:
- Source URL is untrusted input.
- Adapter-specific options must be safe to display or explicitly redacted before logging.
- Parser jobs run under admin-triggered workflow.

## Normalized Output

Each parsed item is normalized into one of these shapes.

### Category draft

```json
{
  "item_type": "category",
  "external_id": "cat-123",
  "source_url": "https://example.com/courses/programming",
  "fingerprint": "normalized-stable-fingerprint",
  "language_code": "en",
  "payload": {
    "name": "Programming"
  }
}
```

### Course draft

```json
{
  "item_type": "course",
  "external_id": "course-456",
  "source_url": "https://example.com/courses/python",
  "fingerprint": "normalized-stable-fingerprint",
  "language_code": "en",
  "payload": {
    "name": "Python Basics",
    "description": "Learn Python from scratch.",
    "category_name": "Programming",
    "price": "49.00",
    "link": "https://example.com/courses/python"
  }
}
```

## Job Result

Parser adapter returns a safe result summary:

```json
{
  "status": "completed",
  "imported_count": 8,
  "skipped_count": 2,
  "errors": []
}
```

Failure result:

```json
{
  "status": "failed",
  "imported_count": 0,
  "skipped_count": 0,
  "errors": [
    "Source returned unsupported content"
  ]
}
```

Rules:
- Error strings must be safe for admin display.
- No credentials, tokens, raw auth headers, or private request data may appear in errors.
- Duplicate external IDs or fingerprints are skipped or marked as possible matches.
- Parsed items are saved as draft/matched, never active public content.
