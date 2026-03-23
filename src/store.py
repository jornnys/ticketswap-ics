# In-memory store (swap for Redis/SQLite in production)
# Maps user_id (hash) → { "url": str, "slug": str, "created_at": float }
USER_STORE: dict[str, dict] = {}

# Simple cache: user_id → { "ics": bytes, "fetched_at": float }
ICS_CACHE: dict[str, dict] = {}

CACHE_TTL_SECONDS = 3600  # 1 hour
