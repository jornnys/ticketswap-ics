import logging
import os

import posthog as _posthog

logger = logging.getLogger(__name__)

_api_key = os.getenv("POSTHOG_API_KEY", "")
_host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")

if _api_key:
    _posthog.api_key = _api_key
    _posthog.host = _host
else:
    logger.warning("POSTHOG_API_KEY not set; analytics disabled")


def capture(event: str, properties: dict | None = None, distinct_id: str = "anonymous") -> None:
    if not _api_key:
        return
    try:
        _posthog.capture(distinct_id, event, properties or {})
    except Exception:
        logger.exception("PostHog capture failed for event %s", event)
