import threading

from cachetools import TTLCache

CACHE_TTL_SECONDS = 3600  # 1 hour

# In-memory store (swap for Redis/SQLite in production)
# Maps user_id (hash) → { "url": str, "slug": str, "created_at": float }
USER_STORE: dict[str, dict] = {}
USER_STORE_LOCK = threading.Lock()

# Bounded TTL cache: auto-expires entries after CACHE_TTL_SECONDS
# Maps user_id → ics bytes
ICS_CACHE: TTLCache = TTLCache(maxsize=1000, ttl=CACHE_TTL_SECONDS)
ICS_CACHE_LOCK = threading.Lock()
