#!/usr/bin/env python3
"""
Update the Lucas section of calendar.ics from the LRGS webcal feed.

The existing Thomas/Harry events in calendar.ics are preserved.
Lucas is filtered to Boys-U14 A/B and Rugby Union/Rugby 7S.
"""

from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta
import re

LRGS_URL = "https://calendar.lrgs.org.uk/CalendarSync.ashx?Cal=Lancaster%20Royal%20Grammar%20School%20Calendar&ID=334&FT=OR&sid=71&sid=24&ST=0"
CALENDAR = Path("calendar.ics")

def unescape(s):
    return (s.replace("\\n","\n").replace("\\N","\n")
             .replace("\\,",",").replace("\\;",";").replace("\\\\","\\"))

def escape(s):
    return (str(s).replace("\\","\\\\").replace(";","\\;")
            .replace(",","\\,").replace("\r\n","\\n")
            .replace("\n","\\n").replace("\r","\\n"))

def get_prop(block, name):
    m = re.search(r"(?mi)^" + re.escape(name) + r"(?:;[^:]*)?:(.*)$", block)
    return unescape(m.group(1).strip()) if m else ""

def parse_dt(value):
    # LRGS feed is UK local time for these school fixtures.
    m = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", value)
    if not m:
        return None
    return datetime(*map(int, m.groups()))

def extract_lucas_events(text):
    events=[]
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        summary=get_prop(block,"SUMMARY")
        if "Boys-U14" not in summary:
            continue
        if not (summary.startswith("Rugby Union ") or summary.startswith("Rugby 7S ")):
            continue

        squad=re.search(r"Boys-U14([A-Z])\b", summary)
        if squad and squad.group(1) not in {"A","B"}:
            continue

        start_value=get_prop(block,"DTSTART")
        start=parse_dt(start_value)
        if not start:
            continue

        ha=get_prop(block,"LOCATION")
        location={"H":"Home","A":"Away"}.get(ha,ha)

        clean=summary.replace("Rugby Union Boys-U14","U14")
        clean=clean.replace("Rugby 7S Boys-U14","U14 7S")
        clean=clean.replace("UU14","U14")

        title=f"Lucas Rugby: {clean}"
        description="Source: LRGS Rugby"
        if location:
            description += f"\nVenue status: {location}"

        uid=f'lucas-{start.strftime("%Y%m%d%H%M")}-{re.sub(r"[^a-z0-9]+","-",clean.lower()).strip("-")}@boys-sports-calendar'

        end=start+timedelta(minutes=90)

        events.append([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;TZID=Europe/London:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID=Europe/London:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{escape(title)}",
            f"LOCATION:{escape(location)}" if location else None,
            f"DESCRIPTION:{escape(description)}",
            "END:VEVENT",
        ])
    return [e for e in events if e]

def remove_lucas(text):
    return re.sub(
        r"BEGIN:VEVENT\r?\n(?:(?!END:VEVENT\r?\n).)*?SUMMARY:Lucas Rugby:.*?END:VEVENT\r?\n?",
        "",
        text,
        flags=re.S
    )

def main():
    if not CALENDAR.exists():
        raise SystemExit("calendar.ics not found")

    req=Request(LRGS_URL, headers={"User-Agent":"Boys-Sports-Calendar/1.0"})
    with urlopen(req, timeout=30) as response:
        remote=response.read().decode("utf-8", errors="replace")

    lucas=extract_lucas_events(remote)
    if not lucas:
        raise SystemExit("No Lucas U14 Rugby events found; refusing to overwrite calendar.")

    current=CALENDAR.read_text(encoding="utf-8")
    current=remove_lucas(current)

    insert="\r\n".join("\r\n".join(e) for e in lucas) + "\r\n"
    current=current.replace("END:VCALENDAR", insert+"END:VCALENDAR")

    CALENDAR.write_text(current, encoding="utf-8")
    print(f"Lucas events updated: {len(lucas)}")

if __name__=="__main__":
    main()
