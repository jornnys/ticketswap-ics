import hashlib
from datetime import datetime, timedelta, timezone

from icalendar import Calendar, Event


def generate_ics(events: list[dict], source_url: str) -> bytes:
    """Convert a list of event dicts to ICS calendar bytes."""
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
            # All-day fallback: end = start + 1 day
            event.add("dtend", ev["start"] + timedelta(days=1))

        if ev.get("location"):
            event.add("location", ev["location"])

        if ev.get("description"):
            event.add("description", ev["description"])

        if ev.get("url"):
            event.add("url", ev["url"])

        # Stable UID so iOS doesn't duplicate events on refresh
        uid_source = (
            f"{ev['title'].strip()}|{ev['start'].isoformat()}"
            f"|{(ev.get('location') or '').strip()}|{(ev.get('url') or '').strip()}"
        )
        uid = hashlib.md5(uid_source.encode()).hexdigest()
        event.add("uid", f"{uid}@ticketswap-ics")

        event.add("dtstamp", datetime.now(timezone.utc))

        cal.add_component(event)

    return cal.to_ical()
