"""
TicketSwap Calendar → ICS Feed converter
MVP: Paste your TicketSwap calendar URL, get a subscribable ICS feed.
"""

import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from icalendar import Calendar, Event
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="TicketSwap → ICS", version="0.1.0")


@app.get("/healthz")
async def health():
    """Health check endpoint for Render."""
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# In-memory store (swap for Redis/SQLite in production)
# ---------------------------------------------------------------------------
# Maps user_id (hash) → { "url": str, "created_at": float }
USER_STORE: dict[str, dict] = {}

# Simple cache: user_id → { "ics": bytes, "fetched_at": float }
ICS_CACHE: dict[str, dict] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    ticketswap_url: str


class RegisterResponse(BaseModel):
    ics_url: str
    webcal_url: str
    user_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Scraper  ← THIS IS THE PART YOU NEED TO FILL IN
# ---------------------------------------------------------------------------
async def scrape_ticketswap_events(url: str) -> list[dict]:
    """
    Scrape events from a TicketSwap calendar page.

    Returns a list of dicts, each with:
        - title: str          (event name)
        - start: datetime     (event start)
        - end: datetime|None  (event end, or None for all-day)
        - location: str|None  (venue name)
        - url: str|None       (link to event on TicketSwap)
        - description: str|None

    -----------------------------------------------------------------------
    TODO: Inspect the TicketSwap page to determine the data source.

    Option A — __NEXT_DATA__ JSON blob:
        Look for <script id="__NEXT_DATA__"> in the HTML.
        Parse JSON → navigate to the events array.

    Option B — API endpoint:
        Open Chrome DevTools → Network tab → reload the page.
        Look for XHR/Fetch calls (often /api/... or /graphql).
        Replicate the request with httpx.

    Option C — Client-side rendered (worst case):
        Use playwright or selenium to render JS, then parse the DOM.
    -----------------------------------------------------------------------
    """

    # --- PLACEHOLDER: returns mock data so the ICS pipeline works ---
    # Replace this with real scraping logic.

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

    # The PublicUser entry holds the favoriteEvents connection
    user = next(
        (v for k, v in apollo.items() if k.startswith("PublicUser:")),
        None,
    )
    if user is None:
        raise ValueError("Could not find user data in TicketSwap page")

    # Key format: favoriteEvents({"after":null,"first":10})
    events_key = next(
        (k for k in user if k.startswith("favoriteEvents(")),
        None,
    )
    if events_key is None:
        return []

    connection = user[events_key]
    edges = connection.get("edges", [])

    # TODO: handle hasNextPage pagination via GraphQL for users with >10 events

    events = []
    for edge in edges:
        ref = edge["node"]["__ref"]
        ev = apollo.get(ref)
        if ev is None:
            continue

        # Resolve location: "Venue Name, City"
        location_str = None
        loc_ref = (ev.get("location") or {}).get("__ref")
        if loc_ref:
            loc = apollo.get(loc_ref, {})
            venue = loc.get("name", "")
            city_ref = (loc.get("city") or {}).get("__ref")
            city = apollo.get(city_ref, {}).get("name", "") if city_ref else ""
            parts = [p for p in [venue, city] if p]
            location_str = ", ".join(parts) or None

        # Build canonical event URL
        event_url = None
        uri_path = (ev.get("uri") or {}).get("path")
        if uri_path:
            # Derive base domain from the original calendar URL
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


# ---------------------------------------------------------------------------
# ICS Generation
# ---------------------------------------------------------------------------
def generate_ics(events: list[dict], source_url: str) -> bytes:
    """Convert a list of event dicts to an ICS calendar bytes."""
    cal = Calendar()
    cal.add("prodid", "-//TicketSwap ICS Feed//ticketswap-ics//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "TicketSwap Events")
    cal.add("x-wr-timezone", "Europe/Brussels")

    for ev in events:
        event = Event()
        event.add("summary", ev["title"])
        event.add("dtstart", ev["start"])

        if ev.get("end"):
            event.add("dtend", ev["end"])
        else:
            # All-day: end = start + 1 day
            event.add("dtend", ev["start"] + timedelta(days=1))

        if ev.get("location"):
            event.add("location", ev["location"])

        if ev.get("description"):
            event.add("description", ev["description"])

        if ev.get("url"):
            event.add("url", ev["url"])

        # Stable UID so iOS doesn't duplicate events on refresh
        uid_source = f"{ev['title']}-{ev['start'].isoformat()}"
        uid = hashlib.md5(uid_source.encode()).hexdigest()
        event.add("uid", f"{uid}@ticketswap-ics")

        event.add("dtstamp", datetime.utcnow())

        cal.add_component(event)

    return cal.to_ical()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/api/register", response_model=RegisterResponse)
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


@app.get("/feed/{user_id}.ics")
async def get_feed(user_id: str):
    """Serve the ICS feed for a registered user. Cached for CACHE_TTL_SECONDS."""
    if user_id not in USER_STORE:
        raise HTTPException(status_code=404, detail="User not found. Register first.")

    # Check cache
    cached = ICS_CACHE.get(user_id)
    if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
        ics_bytes = cached["ics"]
    else:
        # Scrape fresh
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


# ---------------------------------------------------------------------------
# Frontend — single-page landing
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def landing():
    return LANDING_HTML


LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>TicketSwap → Calendar</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#0b0c10; --surface:#151820; --border:#252a36;
    --text:#e4e6ec; --muted:#8a8fa0; --accent:#00d4aa;
    --accent-dim:#00d4aa22; --error:#f05e5e; --font:'DM Sans',sans-serif;
    --mono:'DM Mono',monospace;
  }
  html{font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.6}
  body{min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:2rem 1rem}

  .grain{position:fixed;inset:0;pointer-events:none;opacity:.035;
    background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  .container{max-width:520px;width:100%;margin-top:clamp(2rem,10vh,8rem)}

  h1{font-size:clamp(1.6rem,4vw,2.2rem);font-weight:700;letter-spacing:-.03em;
    line-height:1.15;margin-bottom:.5rem}
  h1 span{color:var(--accent)}
  .subtitle{color:var(--muted);font-size:.95rem;margin-bottom:2.5rem;max-width:38ch}

  .input-group{display:flex;gap:.5rem;margin-bottom:1rem}
  input[type="url"]{flex:1;background:var(--surface);border:1px solid var(--border);
    border-radius:10px;padding:.75rem 1rem;color:var(--text);font-size:.9rem;
    font-family:var(--mono);outline:none;transition:border-color .2s}
  input[type="url"]:focus{border-color:var(--accent)}
  input[type="url"]::placeholder{color:var(--muted);opacity:.6}

  button{background:var(--accent);color:var(--bg);border:none;border-radius:10px;
    padding:.75rem 1.5rem;font-size:.9rem;font-weight:600;cursor:pointer;
    font-family:var(--font);white-space:nowrap;transition:opacity .15s}
  button:hover{opacity:.85}
  button:disabled{opacity:.5;cursor:not-allowed}

  .error{color:var(--error);font-size:.82rem;margin-bottom:1rem;min-height:1.2em}

  .result{background:var(--surface);border:1px solid var(--border);border-radius:14px;
    padding:1.5rem;display:none;animation:fadeIn .3s ease}
  .result.show{display:block}
  .result h2{font-size:.85rem;color:var(--muted);font-weight:500;
    text-transform:uppercase;letter-spacing:.06em;margin-bottom:1rem}
  .feed-url{background:var(--bg);border:1px solid var(--border);border-radius:8px;
    padding:.65rem .85rem;font-family:var(--mono);font-size:.78rem;color:var(--accent);
    word-break:break-all;margin-bottom:1rem;position:relative;cursor:pointer;
    transition:background .15s}
  .feed-url:hover{background:#0d0e13}
  .feed-url .copy-hint{position:absolute;right:.6rem;top:50%;transform:translateY(-50%);
    font-size:.7rem;color:var(--muted);font-family:var(--font)}

  .instructions{color:var(--muted);font-size:.82rem;line-height:1.7}
  .instructions li{margin-bottom:.35rem}
  .instructions code{font-family:var(--mono);color:var(--text);font-size:.78rem;
    background:var(--bg);padding:.15em .4em;border-radius:4px}

  footer{margin-top:auto;padding-top:3rem;color:var(--muted);font-size:.75rem;
    text-align:center;opacity:.5}

  @keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
</style>
</head>
<body>
<div class="grain"></div>

<div class="container">
  <h1>TicketSwap → <span>Calendar</span></h1>
  <p class="subtitle">
    Paste your TicketSwap calendar URL and get an ICS feed you can subscribe to in iOS, Google Calendar, or Outlook.
  </p>

  <div class="input-group">
    <input type="url" id="url-input"
           placeholder="https://www.ticketswap.be/user/.../events-calendar"
           spellcheck="false" autocomplete="off"/>
    <button id="submit-btn" onclick="handleSubmit()">Get feed</button>
  </div>
  <div class="error" id="error"></div>

  <div class="result" id="result">
    <h2>Your ICS feed</h2>

    <div class="feed-url" id="webcal-url" onclick="copyUrl('webcal')" title="Click to copy">
      <span id="webcal-text"></span>
      <span class="copy-hint">copy</span>
    </div>

    <div class="feed-url" id="https-url" onclick="copyUrl('https')" title="Click to copy">
      <span id="https-text"></span>
      <span class="copy-hint">copy</span>
    </div>

    <h2 style="margin-top:1.25rem">How to subscribe</h2>
    <ol class="instructions">
      <li><strong>iPhone/iPad:</strong> Go to <code>Settings</code> → <code>Calendar</code> → <code>Accounts</code> → <code>Add Account</code> → <code>Other</code> → <code>Add Subscribed Calendar</code> → paste the <code>webcal://</code> URL.</li>
      <li><strong>Google Calendar:</strong> Other calendars → <code>From URL</code> → paste the <code>https://</code> URL.</li>
      <li><strong>Outlook:</strong> Add calendar → <code>Subscribe from web</code> → paste the <code>https://</code> URL.</li>
    </ol>
  </div>
</div>

<footer>Not affiliated with TicketSwap. Open source side-project.</footer>

<script>
const inp = document.getElementById('url-input');
const btn = document.getElementById('submit-btn');
const err = document.getElementById('error');
const res = document.getElementById('result');

let feedUrls = {};

async function handleSubmit() {
  err.textContent = '';
  res.classList.remove('show');
  btn.disabled = true;
  btn.textContent = 'Loading…';

  try {
    const resp = await fetch('/api/register', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ticketswap_url: inp.value.trim() })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Something went wrong');

    feedUrls = { webcal: data.webcal_url, https: data.ics_url };
    document.getElementById('webcal-text').textContent = data.webcal_url;
    document.getElementById('https-text').textContent = data.ics_url;
    res.classList.add('show');
  } catch (e) {
    err.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Get feed';
  }
}

function copyUrl(type) {
  const url = feedUrls[type];
  if (!url) return;
  navigator.clipboard.writeText(url).then(() => {
    const el = document.getElementById(type === 'webcal' ? 'webcal-url' : 'https-url');
    const hint = el.querySelector('.copy-hint');
    hint.textContent = 'copied!';
    setTimeout(() => hint.textContent = 'copy', 1500);
  });
}

inp.addEventListener('keydown', e => { if (e.key === 'Enter') handleSubmit(); });
</script>
</body>
</html>
"""
