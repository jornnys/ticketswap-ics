import hashlib
import json
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

TICKETSWAP_URL_PATTERN = re.compile(
    r"https?://(www\.)?ticketswap\.(com|be|nl|de|fr|es|it|at|pt)/user/([A-Za-z0-9_-]+)/events-calendar"
)


def extract_user_slug(url: str) -> str:
    """Extract the TicketSwap user slug from the calendar URL."""
    match = TICKETSWAP_URL_PATTERN.match(url.strip())
    if not match:
        raise ValueError(
            "Invalid TicketSwap calendar URL. "
            "Expected format: https://www.ticketswap.be/user/<id>/events-calendar"
        )
    return match.group(3)


def make_user_id(slug: str) -> str:
    """Create a short, URL-safe user ID from the slug."""
    return hashlib.sha256(slug.encode()).hexdigest()[:12]


async def scrape_ticketswap_events(url: str) -> list[dict]:
    """
    Scrape events from a TicketSwap calendar page via __NEXT_DATA__.

    Returns a list of dicts, each with:
        - title: str
        - start: datetime
        - end: datetime | None
        - location: str | None
        - url: str | None
        - description: str | None

    TODO: handle hasNextPage pagination via GraphQL for users with >10 events.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if not next_data_tag:
        raise ValueError("Could not find __NEXT_DATA__ on TicketSwap page")

    data = json.loads(next_data_tag.string)
    apollo: dict = data["props"]["pageProps"]["initialApolloState"]

    user = next(
        (v for k, v in apollo.items() if k.startswith("PublicUser:")),
        None,
    )
    if user is None:
        raise ValueError("Could not find user data in TicketSwap page")

    events_key = next(
        (k for k in user if k.startswith("favoriteEvents(")),
        None,
    )
    if events_key is None:
        return []

    edges = user[events_key].get("edges", [])
    events = []

    for edge in edges:
        ref = edge["node"]["__ref"]
        ev = apollo.get(ref)
        if ev is None:
            continue

        location_str = None
        loc_ref = (ev.get("location") or {}).get("__ref")
        if loc_ref:
            loc = apollo.get(loc_ref, {})
            venue = loc.get("name", "")
            city_ref = (loc.get("city") or {}).get("__ref")
            city = apollo.get(city_ref, {}).get("name", "") if city_ref else ""
            parts = [p for p in [venue, city] if p]
            location_str = ", ".join(parts) or None

        event_url = None
        uri_path = (ev.get("uri") or {}).get("path")
        if uri_path:
            domain_match = re.match(r"(https?://(?:www\.)?ticketswap\.[a-z]+)", url)
            base = domain_match.group(1) if domain_match else "https://www.ticketswap.be"
            event_url = f"{base}{uri_path}"

        start = datetime.fromisoformat(ev["startDate"])
        end = datetime.fromisoformat(ev["endDate"]) if ev.get("endDate") else None

        events.append({
            "title": ev["name"],
            "start": start,
            "end": end,
            "location": location_str,
            "url": event_url,
            "description": None,
        })

    return events
