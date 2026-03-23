# TicketSwap → ICS Calendar Feed

Convert your TicketSwap events calendar into a subscribable ICS feed for iOS Calendar, Google Calendar, or Outlook.

## Quick start (local)

```bash
uv sync
PYTHONPATH=src uv run uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000), paste your TicketSwap calendar URL, and get your ICS feed link.

## How it works

1. Paste your TicketSwap calendar URL (`https://www.ticketswap.be/user/<id>/events-calendar`)
2. The app registers it and returns a personal ICS feed URL
3. `GET /feed/{user_id}.ics` scrapes the TicketSwap page, parses events from `__NEXT_DATA__` Apollo state, and serves a valid ICS file
4. Your calendar app polls the feed periodically — events stay in sync automatically

## API

```
GET  /                      Landing page
POST /api/register          Register a TicketSwap URL → returns ICS + webcal URLs
GET  /feed/{user_id}.ics    Scrape & serve ICS feed (cached 1h)
GET  /healthz               Health check
```

## Tech stack

- **FastAPI** — async web framework
- **httpx** — async HTTP client for scraping
- **BeautifulSoup4** — HTML parsing
- **icalendar** — ICS generation
- **uvicorn** — ASGI server
- **uv** — dependency management
