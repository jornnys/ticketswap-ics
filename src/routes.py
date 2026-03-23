import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from analytics import capture
from frontend import LANDING_HTML
from ics import generate_ics
from models import RegisterRequest, RegisterResponse
from scraper import extract_user_slug, make_user_id, scrape_ticketswap_events
from store import ICS_CACHE, ICS_CACHE_LOCK, USER_STORE, USER_STORE_LOCK

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/healthz")
async def health():
    """Health check endpoint for Render."""
    return {"status": "ok"}


class TrackRequest(BaseModel):
    event: str
    properties: dict = {}


@router.post("/api/track", status_code=204)
async def track(body: TrackRequest):
    """Receive a client-side analytics event and forward it to PostHog."""
    allowed = {"ics_link_copied"}
    if body.event in allowed:
        capture(body.event, body.properties)


@router.post("/api/register", response_model=RegisterResponse)
async def register(body: RegisterRequest, request: Request):
    """Register a TicketSwap calendar URL and get back an ICS feed URL."""
    url_str = str(body.ticketswap_url)
    try:
        slug = extract_user_slug(url_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_id = make_user_id(slug)
    capture("link_submitted", distinct_id=user_id)
    with USER_STORE_LOCK:
        USER_STORE[user_id] = {
            "url": url_str.strip(),
            "slug": slug,
            "created_at": time.time(),
        }

    base_url = str(request.base_url).rstrip("/")
    ics_path = f"/feed/{user_id}.ics"
    host = request.base_url.netloc

    return RegisterResponse(
        ics_url=f"{base_url}{ics_path}",
        webcal_url=f"webcal://{host}{ics_path}",
        user_id=user_id,
    )


@router.get("/feed/{user_id}.ics")
async def get_feed(user_id: str):
    """Serve the ICS feed for a registered user. Cached for CACHE_TTL_SECONDS."""
    with USER_STORE_LOCK:
        if user_id not in USER_STORE:
            raise HTTPException(status_code=404, detail="User not found. Register first.")
        url = USER_STORE[user_id]["url"]

    with ICS_CACHE_LOCK:
        ics_bytes = ICS_CACHE.get(user_id)

    if ics_bytes is None:
        try:
            events = await scrape_ticketswap_events(url)
        except Exception:
            logger.exception("Failed to scrape TicketSwap events for user %s", user_id)
            raise HTTPException(status_code=502, detail="Failed to fetch TicketSwap data")

        ics_bytes = generate_ics(events, url)
        with ICS_CACHE_LOCK:
            ICS_CACHE[user_id] = ics_bytes

    return Response(
        content=ics_bytes,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{user_id}.ics"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/", response_class=HTMLResponse)
async def landing():
    capture("page_viewed")
    return LANDING_HTML
