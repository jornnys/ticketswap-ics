# TicketSwap → ICS Calendar Feed

Convert your TicketSwap events calendar into a subscribable ICS feed for iOS Calendar, Google Calendar, or Outlook.

**Live at [ticketswap-ics.onrender.com](https://ticketswap-ics.onrender.com)**

## Quick start (local)

```bash
uv sync
uv run uvicorn main:app --reload --port 8000
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
POST /api/track             Client-side analytics proxy
GET  /healthz               Health check
```

## Analytics

Usage is tracked via [PostHog](https://posthog.com). Three events are captured:

| Event | Trigger |
|---|---|
| `page_viewed` | Someone visits the landing page |
| `link_submitted` | Someone submits a TicketSwap URL |
| `ics_link_copied` | Someone copies a generated ICS/webcal link |

A persistent UUID is set as a `uid` cookie (1-year, HttpOnly) on first visit so all events from the same browser share one `distinct_id` in PostHog.

Analytics are disabled when `POSTHOG_API_KEY` is not set.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `POSTHOG_API_KEY` | — | PostHog project API key (required to enable analytics) |
| `POSTHOG_HOST` | `https://us.i.posthog.com` | PostHog ingest host (use `https://eu.i.posthog.com` for EU) |

## Tech stack

- **FastAPI** — async web framework
- **httpx** — async HTTP client for scraping
- **BeautifulSoup4** — HTML parsing
- **icalendar** — ICS generation
- **posthog** — analytics
- **uvicorn** — ASGI server
- **uv** — dependency management
