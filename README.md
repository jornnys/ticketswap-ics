# TicketSwap → ICS Calendar Feed

Convert your TicketSwap events calendar into a subscribable ICS feed for iOS Calendar, Google Calendar, or Outlook.

## Quick start (local)

```bash
# Install dependencies
uv sync

# Run the server
uv run uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000), paste your TicketSwap calendar URL, and get your ICS feed link.

## How it works

1. User pastes their TicketSwap calendar URL (e.g. `https://www.ticketswap.be/user/.../events-calendar`)
2. The API generates a unique ICS feed URL
3. The `/feed/{id}.ics` endpoint scrapes the TicketSwap page, converts events to ICS format, and serves it with `text/calendar` content type
4. iOS/Google/Outlook polls this endpoint periodically → calendar stays in sync

## TODO: Implement the scraper

The scraper in `main.py` → `scrape_ticketswap_events()` currently returns **mock data**. To make it work:

1. Open your TicketSwap calendar page in Chrome
2. Open DevTools (F12) → Network tab → reload the page
3. Look for:
   - **`__NEXT_DATA__`** in the HTML source (View Source → Ctrl+F)
   - **API calls** in the Network tab (filter by XHR/Fetch)
4. Once you know the data structure, fill in Strategy A, B, or C in the scraper function

## Deploy to Render (free tier)

### Option A: One-click via render.yaml

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your repo — Render picks up `render.yaml` automatically
4. Done. You get a URL like `https://ticketswap-ics.onrender.com`

### Option B: Manual setup

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect your repo
4. Settings:
   - **Runtime**: Docker
   - **Plan**: Free
   - **Branch**: main
5. Deploy

### Free tier notes

- Service spins down after 15 min of inactivity
- First request after spin-down takes ~30s (cold start)
- Since iOS polls the ICS feed every few hours, the service stays warm enough
- 750 hours/month free — more than enough for a side project

### Optional: custom domain

In the Render dashboard → your service → **Settings** → **Custom Domains** → add your domain and update DNS.

## Architecture

```
GET /                    → Landing page (HTML form)
POST /api/register       → Register URL, get ICS feed link
GET /feed/{user_id}.ics  → Scrape + generate ICS (cached 1h)
```

## Tech stack

- **uv** — fast Python package manager
- **FastAPI** — async web framework
- **httpx** — async HTTP client for scraping
- **BeautifulSoup4** — HTML parsing
- **icalendar** — ICS file generation
- **uvicorn** — ASGI server
