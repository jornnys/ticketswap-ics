import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from frontend import LANDING_HTML
from ics import generate_ics
from models import RegisterRequest, RegisterResponse
from scraper import extract_user_slug, make_user_id, scrape_ticketswap_events
from store import CACHE_TTL_SECONDS, ICS_CACHE, USER_STORE

router = APIRouter()


@router.get("/healthz")
async def health():
    """Health check endpoint for Render."""
    return {"status": "ok"}


@router.post("/api/register", response_model=RegisterResponse)
async def register(body: RegisterRequest, request: Request):
    """Register a TicketSwap calendar URL and get back an ICS feed URL."""
    try:
        slug = extract_user_slug(body.ticketswap_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_id = make_user_id(slug)
    USER_STORE[user_id] = {
        "url": body.ticketswap_url.strip(),
        "slug": slug,
        "created_at": time.time(),
    }

    base_url = str(request.base_url).rstrip("/")
    ics_path = f"/feed/{user_id}.ics"

    return RegisterResponse(
        ics_url=f"{base_url}{ics_path}",
        webcal_url=f"webcal://{request.headers.get('host', 'localhost')}{ics_path}",
        user_id=user_id,
    )


@router.get("/feed/{user_id}.ics")
async def get_feed(user_id: str):
    """Serve the ICS feed for a registered user. Cached for CACHE_TTL_SECONDS."""
    if user_id not in USER_STORE:
        raise HTTPException(status_code=404, detail="User not found. Register first.")

    cached = ICS_CACHE.get(user_id)
    if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
        ics_bytes = cached["ics"]
    else:
        url = USER_STORE[user_id]["url"]
        try:
            events = await scrape_ticketswap_events(url)
        except Exception as e:
            raise HTTPException(
                status_code=502, detail=f"Failed to fetch TicketSwap data: {e}"
            )

        ics_bytes = generate_ics(events, url)
        ICS_CACHE[user_id] = {"ics": ics_bytes, "fetched_at": time.time()}

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
    return LANDING_HTML
