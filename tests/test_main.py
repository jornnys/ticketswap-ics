"""Tests for ticketswap-ics."""

import hashlib
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from icalendar import Calendar

from main import app
from store import USER_STORE, ICS_CACHE
from scraper import extract_user_slug, make_user_id, scrape_ticketswap_events
from ics import generate_ics

client = TestClient(app)

VALID_URL = "https://www.ticketswap.be/user/PB0u3ewIJkFSug6OyAo42VNRfLaA08XUykupipbM0GDBA0pG3x/events-calendar"
VALID_SLUG = "PB0u3ewIJkFSug6OyAo42VNRfLaA08XUykupipbM0GDBA0pG3x"

SAMPLE_EVENTS = [
    {
        "title": "Tomorrowland 2026",
        "start": datetime(2026, 7, 18, 12, 0),
        "end": datetime(2026, 7, 18, 23, 0),
        "location": "Boom, Belgium",
        "url": "https://www.ticketswap.be/event/tomorrowland-2026",
        "description": "Weekend 1",
    },
    {
        "title": "Concert no end",
        "start": datetime(2026, 8, 1, 20, 0),
        "end": None,
        "location": None,
        "url": None,
        "description": None,
    },
]


# ---------------------------------------------------------------------------
# extract_user_slug
# ---------------------------------------------------------------------------
class TestExtractUserSlug:
    def test_valid_be_url(self):
        assert extract_user_slug(VALID_URL) == VALID_SLUG

    def test_valid_com_url(self):
        url = "https://www.ticketswap.com/user/abc123/events-calendar"
        assert extract_user_slug(url) == "abc123"

    def test_valid_nl_url(self):
        url = "https://ticketswap.nl/user/myslug/events-calendar"
        assert extract_user_slug(url) == "myslug"

    def test_strips_whitespace(self):
        assert extract_user_slug(f"  {VALID_URL}  ") == VALID_SLUG

    def test_invalid_domain(self):
        with pytest.raises(ValueError, match="Invalid TicketSwap"):
            extract_user_slug("https://www.evil.com/user/abc/events-calendar")

    def test_missing_events_calendar_suffix(self):
        with pytest.raises(ValueError):
            extract_user_slug("https://www.ticketswap.be/user/abc123")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            extract_user_slug("")

    def test_plain_text(self):
        with pytest.raises(ValueError):
            extract_user_slug("not-a-url")


# ---------------------------------------------------------------------------
# make_user_id
# ---------------------------------------------------------------------------
class TestMakeUserId:
    def test_returns_12_chars(self):
        assert len(make_user_id(VALID_SLUG)) == 12

    def test_deterministic(self):
        assert make_user_id(VALID_SLUG) == make_user_id(VALID_SLUG)

    def test_different_slugs_differ(self):
        assert make_user_id("slug_a") != make_user_id("slug_b")

    def test_alphanumeric(self):
        uid = make_user_id(VALID_SLUG)
        assert uid.isalnum()


# ---------------------------------------------------------------------------
# generate_ics
# ---------------------------------------------------------------------------
class TestGenerateIcs:
    def _parse(self, ics_bytes: bytes) -> Calendar:
        return Calendar.from_ical(ics_bytes)

    def test_returns_bytes(self):
        result = generate_ics(SAMPLE_EVENTS, VALID_URL)
        assert isinstance(result, bytes)

    def test_valid_ical(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        assert cal.get("version") == "2.0"

    def test_event_count(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        assert len(events) == 2

    def test_event_fields(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        titles = {str(e.get("summary")) for e in events}
        assert "Tomorrowland 2026" in titles
        assert "Concert no end" in titles

    def test_location_set(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        tomorrowland = next(
            c for c in cal.walk()
            if c.name == "VEVENT" and str(c.get("summary")) == "Tomorrowland 2026"
        )
        assert str(tomorrowland.get("location")) == "Boom, Belgium"

    def test_no_end_falls_back_to_allday(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        no_end = next(
            c for c in cal.walk()
            if c.name == "VEVENT" and str(c.get("summary")) == "Concert no end"
        )
        dtstart = no_end.decoded("dtstart")
        dtend = no_end.decoded("dtend")
        from datetime import timedelta
        assert dtend == dtstart + timedelta(days=1)

    def test_stable_uid(self):
        """Same event produces same UID across calls."""
        ics1 = generate_ics([SAMPLE_EVENTS[0]], VALID_URL)
        ics2 = generate_ics([SAMPLE_EVENTS[0]], VALID_URL)
        cal1 = self._parse(ics1)
        cal2 = self._parse(ics2)
        uid1 = next(c.get("uid") for c in cal1.walk() if c.name == "VEVENT")
        uid2 = next(c.get("uid") for c in cal2.walk() if c.name == "VEVENT")
        assert str(uid1) == str(uid2)

    def test_empty_events(self):
        ics = generate_ics([], VALID_URL)
        cal = self._parse(ics)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        assert events == []

    def test_url_field_set(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        tomorrowland = next(
            c for c in cal.walk()
            if c.name == "VEVENT" and str(c.get("summary")) == "Tomorrowland 2026"
        )
        assert str(tomorrowland.get("url")) == "https://www.ticketswap.be/event/tomorrowland-2026"

    def test_url_field_absent_when_none(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        no_url = next(
            c for c in cal.walk()
            if c.name == "VEVENT" and str(c.get("summary")) == "Concert no end"
        )
        assert no_url.get("url") is None

    def test_description_field_set(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        tomorrowland = next(
            c for c in cal.walk()
            if c.name == "VEVENT" and str(c.get("summary")) == "Tomorrowland 2026"
        )
        assert str(tomorrowland.get("description")) == "Weekend 1"

    def test_description_absent_when_none(self):
        ics = generate_ics(SAMPLE_EVENTS, VALID_URL)
        cal = self._parse(ics)
        no_desc = next(
            c for c in cal.walk()
            if c.name == "VEVENT" and str(c.get("summary")) == "Concert no end"
        )
        assert no_desc.get("description") is None

    def test_calendar_properties(self):
        ics = generate_ics([], VALID_URL)
        cal = self._parse(ics)
        assert "ticketswap-ics" in str(cal.get("prodid")).lower()
        assert str(cal.get("calscale")) == "GREGORIAN"
        assert str(cal.get("x-wr-calname")) == "TicketSwap Events"

    def test_uid_stable_when_location_changes(self):
        """Changing location must NOT change UID (backward compat)."""
        event_a = {**SAMPLE_EVENTS[0], "location": "Boom, Belgium"}
        event_b = {**SAMPLE_EVENTS[0], "location": "Completely Different Venue"}
        ics_a = generate_ics([event_a], VALID_URL)
        ics_b = generate_ics([event_b], VALID_URL)
        uid_a = next(str(c.get("uid")) for c in self._parse(ics_a).walk() if c.name == "VEVENT")
        uid_b = next(str(c.get("uid")) for c in self._parse(ics_b).walk() if c.name == "VEVENT")
        assert uid_a == uid_b

    def test_uid_stable_when_url_changes(self):
        """Changing url must NOT change UID (backward compat)."""
        event_a = {**SAMPLE_EVENTS[0], "url": "https://www.ticketswap.be/event/original"}
        event_b = {**SAMPLE_EVENTS[0], "url": "https://www.ticketswap.be/event/changed"}
        ics_a = generate_ics([event_a], VALID_URL)
        ics_b = generate_ics([event_b], VALID_URL)
        uid_a = next(str(c.get("uid")) for c in self._parse(ics_a).walk() if c.name == "VEVENT")
        uid_b = next(str(c.get("uid")) for c in self._parse(ics_b).walk() if c.name == "VEVENT")
        assert uid_a == uid_b


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------
class TestHealth:
    def test_ok(self):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /api/register
# ---------------------------------------------------------------------------
class TestRegister:
    def setup_method(self):
        USER_STORE.clear()
        ICS_CACHE.clear()

    def test_valid_url_returns_200(self):
        resp = client.post("/api/register", json={"ticketswap_url": VALID_URL})
        assert resp.status_code == 200

    def test_response_contains_ics_url(self):
        resp = client.post("/api/register", json={"ticketswap_url": VALID_URL})
        data = resp.json()
        assert data["ics_url"].endswith(".ics")

    def test_response_contains_webcal_url(self):
        resp = client.post("/api/register", json={"ticketswap_url": VALID_URL})
        data = resp.json()
        assert data["webcal_url"].startswith("webcal://")

    def test_response_contains_user_id(self):
        resp = client.post("/api/register", json={"ticketswap_url": VALID_URL})
        data = resp.json()
        assert len(data["user_id"]) == 12

    def test_same_url_same_user_id(self):
        r1 = client.post("/api/register", json={"ticketswap_url": VALID_URL})
        r2 = client.post("/api/register", json={"ticketswap_url": VALID_URL})
        assert r1.json()["user_id"] == r2.json()["user_id"]

    def test_invalid_domain_returns_400(self):
        resp = client.post("/api/register", json={"ticketswap_url": "https://google.com"})
        assert resp.status_code == 400

    def test_invalid_domain_error_message(self):
        resp = client.post("/api/register", json={"ticketswap_url": "https://google.com"})
        assert "Invalid" in resp.json()["detail"]

    def test_non_url_returns_422(self):
        # Pydantic rejects non-URLs before they reach our handler
        resp = client.post("/api/register", json={"ticketswap_url": "bad"})
        assert resp.status_code == 422

    def test_user_stored(self):
        client.post("/api/register", json={"ticketswap_url": VALID_URL})
        uid = make_user_id(VALID_SLUG)
        assert uid in USER_STORE
        assert USER_STORE[uid]["url"] == VALID_URL


# ---------------------------------------------------------------------------
# /feed/{user_id}.ics
# ---------------------------------------------------------------------------
class TestFeed:
    def setup_method(self):
        USER_STORE.clear()
        ICS_CACHE.clear()

    def _register(self) -> str:
        resp = client.post("/api/register", json={"ticketswap_url": VALID_URL})
        return resp.json()["user_id"]

    def test_unknown_user_404(self):
        resp = client.get("/feed/doesnotexist.ics")
        assert resp.status_code == 404

    def test_returns_ics_content_type(self):
        uid = self._register()
        with patch("routes.scrape_ticketswap_events", new=AsyncMock(return_value=SAMPLE_EVENTS)):
            resp = client.get(f"/feed/{uid}.ics")
        assert resp.status_code == 200
        assert "text/calendar" in resp.headers["content-type"]

    def test_ics_body_is_valid(self):
        uid = self._register()
        with patch("routes.scrape_ticketswap_events", new=AsyncMock(return_value=SAMPLE_EVENTS)):
            resp = client.get(f"/feed/{uid}.ics")
        cal = Calendar.from_ical(resp.content)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        assert len(events) == 2

    def test_scraper_error_returns_502(self):
        uid = self._register()
        with patch(
            "routes.scrape_ticketswap_events",
            new=AsyncMock(side_effect=Exception("network error")),
        ):
            resp = client.get(f"/feed/{uid}.ics")
        assert resp.status_code == 502

    def test_cache_is_used_on_second_request(self):
        uid = self._register()
        mock_scrape = AsyncMock(return_value=SAMPLE_EVENTS)
        with patch("routes.scrape_ticketswap_events", new=mock_scrape):
            client.get(f"/feed/{uid}.ics")
            client.get(f"/feed/{uid}.ics")
        # scraper called only once despite two requests
        assert mock_scrape.call_count == 1

    def test_content_disposition_header(self):
        uid = self._register()
        with patch("routes.scrape_ticketswap_events", new=AsyncMock(return_value=SAMPLE_EVENTS)):
            resp = client.get(f"/feed/{uid}.ics")
        assert uid in resp.headers["content-disposition"]

    def test_cache_control_header(self):
        uid = self._register()
        with patch("routes.scrape_ticketswap_events", new=AsyncMock(return_value=SAMPLE_EVENTS)):
            resp = client.get(f"/feed/{uid}.ics")
        assert "public" in resp.headers["cache-control"]
        assert "max-age=3600" in resp.headers["cache-control"]


# ---------------------------------------------------------------------------
# / landing page
# ---------------------------------------------------------------------------
class TestLanding:
    def test_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_contains_form(self):
        resp = client.get("/")
        assert "ticketswap" in resp.text.lower()

    def test_has_url_input(self):
        resp = client.get("/")
        assert 'type="url"' in resp.text

    def test_no_google_fonts(self):
        resp = client.get("/")
        assert "fonts.googleapis.com" not in resp.text


# ---------------------------------------------------------------------------
# scrape_ticketswap_events
# ---------------------------------------------------------------------------
def _make_next_data_html(apollo: dict) -> str:
    """Wrap an Apollo state dict in a minimal Next.js __NEXT_DATA__ page."""
    payload = {
        "props": {
            "pageProps": {
                "initialApolloState": apollo,
            }
        }
    }
    return f'<html><body><script id="__NEXT_DATA__">{json.dumps(payload)}</script></body></html>'


def _fake_apollo(*, has_next: bool = False) -> dict:
    return {
        "ROOT_QUERY": {},
        "PublicUser:abc": {
            "__typename": "PublicUser",
            "id": "abc",
            'favoriteEvents({"after":null,"first":10})': {
                "__typename": "EventConnection",
                "pageInfo": {
                    "__typename": "PageInfo",
                    "hasNextPage": has_next,
                    "endCursor": "cursor1",
                },
                "edges": [
                    {"__typename": "EventEdge", "node": {"__ref": "Event:1"}},
                    {"__typename": "EventEdge", "node": {"__ref": "Event:2"}},
                ],
            },
        },
        "Event:1": {
            "__typename": "Event",
            "id": "Event:1",
            "name": "Thundercat",
            "startDate": "2026-03-23T19:00:00+01:00",
            "endDate": "2026-03-23T22:30:00+01:00",
            "location": {"__ref": "Location:10"},
            "uri": {"__typename": "Uri", "path": "/concert-tickets/thundercat-brussels-2026"},
        },
        "Event:2": {
            "__typename": "Event",
            "id": "Event:2",
            "name": "No Location Event",
            "startDate": "2026-05-01T20:00:00+02:00",
            "endDate": None,
            "location": None,
            "uri": None,
        },
        "Location:10": {
            "__typename": "Location",
            "id": "Location:10",
            "name": "Ancienne Belgique",
            "city": {"__ref": "City:4"},
        },
        "City:4": {
            "__typename": "City",
            "id": "City:4",
            "name": "Brussels",
        },
    }


def _mock_httpx(html: str):
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


class TestScraper:
    @pytest.fixture
    def mock_client(self):
        html = _make_next_data_html(_fake_apollo())
        mc = _mock_httpx(html)
        with patch("httpx.AsyncClient", return_value=mc):
            yield

    @pytest.mark.asyncio
    async def test_returns_list(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_event_count(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_event_title(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert events[0]["title"] == "Thundercat"

    @pytest.mark.asyncio
    async def test_event_start_is_datetime(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert isinstance(events[0]["start"], datetime)

    @pytest.mark.asyncio
    async def test_event_end_is_datetime(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert isinstance(events[0]["end"], datetime)

    @pytest.mark.asyncio
    async def test_location_resolved(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert events[0]["location"] == "Ancienne Belgique, Brussels"

    @pytest.mark.asyncio
    async def test_url_resolved(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert events[0]["url"] == "https://www.ticketswap.be/concert-tickets/thundercat-brussels-2026"

    @pytest.mark.asyncio
    async def test_missing_location_is_none(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert events[1]["location"] is None

    @pytest.mark.asyncio
    async def test_missing_uri_is_none(self, mock_client):
        events = await scrape_ticketswap_events(VALID_URL)
        assert events[1]["url"] is None

    @pytest.mark.asyncio
    async def test_missing_next_data_raises(self):
        mc = _mock_httpx("<html><body>no data here</body></html>")
        with patch("httpx.AsyncClient", return_value=mc):
            with pytest.raises(ValueError, match="__NEXT_DATA__"):
                await scrape_ticketswap_events(VALID_URL)

    @pytest.mark.asyncio
    async def test_empty_edges_returns_empty_list(self):
        apollo = _fake_apollo()
        user = apollo["PublicUser:abc"]
        key = next(k for k in user if k.startswith("favoriteEvents("))
        user[key]["edges"] = []
        mc = _mock_httpx(_make_next_data_html(apollo))
        with patch("httpx.AsyncClient", return_value=mc):
            events = await scrape_ticketswap_events(VALID_URL)
        assert events == []

    @pytest.mark.asyncio
    async def test_no_user_key_raises(self):
        """Apollo state with no PublicUser: key should raise ValueError."""
        apollo = _fake_apollo()
        del apollo["PublicUser:abc"]
        mc = _mock_httpx(_make_next_data_html(apollo))
        with patch("httpx.AsyncClient", return_value=mc):
            with pytest.raises(ValueError, match="user data"):
                await scrape_ticketswap_events(VALID_URL)

    @pytest.mark.asyncio
    async def test_no_favorite_events_key_returns_empty(self):
        """User object with no favoriteEvents key should return empty list."""
        apollo = _fake_apollo()
        key = next(k for k in apollo["PublicUser:abc"] if k.startswith("favoriteEvents("))
        del apollo["PublicUser:abc"][key]
        mc = _mock_httpx(_make_next_data_html(apollo))
        with patch("httpx.AsyncClient", return_value=mc):
            events = await scrape_ticketswap_events(VALID_URL)
        assert events == []

    @pytest.mark.asyncio
    async def test_event_end_none_when_missing(self, mock_client):
        """Event with no endDate should have end=None."""
        events = await scrape_ticketswap_events(VALID_URL)
        no_end = next(e for e in events if e["title"] == "No Location Event")
        assert no_end["end"] is None
