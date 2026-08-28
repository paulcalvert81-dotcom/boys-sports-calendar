#!/usr/bin/env python3

from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta
import re
import html

CALENDAR = Path("calendar.ics")

TEAMS = {
    "Thomas Football": {
        "url": "https://fulltime.thefa.com/displayTeam.html?id=403458042",
        "team": "Heysham Blue Star U12",
    },
    "Harry Football": {
        "url": "https://fulltime.thefa.com/displayTeam.html?divisionseason=358442230&teamID=582569048",
        "team": "Heysham Blue Star U9",
    },
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/142.0.0.0 Safari/537.36"
)


def clean_text(value):
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fetch_page(url):
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )

    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_cell(row, css_class):
    pattern = (
        r'<td[^>]*class="[^"]*'
        + re.escape(css_class)
        + r'[^"]*"[^>]*>(.*?)</td>'
    )

    match = re.search(
        pattern,
        row,
        flags=re.S | re.I,
    )

    if not match:
        return ""

    return clean_text(match.group(1))


def extract_fixture_rows(page):
    return re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        page,
        flags=re.S | re.I,
    )


def extract_fixtures(page, team_name, calendar_name):
    fixtures = []

    for row in extract_fixture_rows(page):

        if team_name not in row:
            continue

        date_match = re.search(
            r'<span[^>]*class="[^"]*spacer-right[^"]*"[^>]*>'
            r'\s*(\d{2}/\d{2}/\d{2})\s*'
            r'</span>\s*'
            r'<span[^>]*>\s*(\d{1,2}:\d{2})\s*</span>',
            row,
            flags=re.S | re.I,
        )

        if not date_match:
            continue

        date_text = date_match.group(1)
        time_text = date_match.group(2)

        home = extract_cell(row, "home-team")
        away = extract_cell(row, "road-team")

        cells = re.findall(
            r"<td[^>]*>(.*?)</td>",
            row,
            flags=re.S | re.I,
        )

        venue = ""

        if len(cells) >= 8:
            venue = clean_text(cells[-1])

        if not home or not away:
            continue

        if team_name not in home and team_name not in away:
            continue

        try:
            start = datetime.strptime(
                f"{date_text} {time_text}",
                "%d/%m/%y %H:%M",
            )
        except ValueError:
            continue

        end = start + timedelta(minutes=90)

        title = (
            f"{calendar_name}: "
            f"{home} v {away}"
        )

        uid_slug = re.sub(
            r"[^a-z0-9]+",
            "-",
            f"{calendar_name}-{date_text}-{home}-{away}".lower(),
        ).strip("-")

        uid = (
            f"{uid_slug}@boys-sports-calendar"
        )

        event = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            (
                "DTSTAMP:"
                f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            ),
            (
                "DTSTART;TZID=Europe/London:"
                f"{start.strftime('%Y%m%dT%H%M%S')}"
            ),
            (
                "DTEND;TZID=Europe/London:"
                f"{end.strftime('%Y%m%dT%H%M%S')}"
            ),
            f"SUMMARY:{escape(title)}",
        ]

        if venue:
            event.append(
                f"LOCATION:{escape(venue)}"
            )

        event.extend([
            "DESCRIPTION:Source: FA Full-Time",
            "END:VEVENT",
        ])

        fixtures.append(event)

    return fixtures


def remove_fulltime_events(calendar):
    return re.sub(
        r"BEGIN:VEVENT\r?\n"
        r"(?:(?!END:VEVENT\r?\n).)*?"
        r"SUMMARY:(?:Thomas Football|Harry Football):.*?"
        r"END:VEVENT\r?\n?",
        "",
        calendar,
        flags=re.S | re.I,
    )


def main():

    if not CALENDAR.exists():
        raise SystemExit(
            "calendar.ics not found"
        )

    all_events = []

    for calendar_name, info in TEAMS.items():

        print(
            f"Downloading {calendar_name}..."
        )

        page = fetch_page(info["url"])

        if info["team"] not in page:
            raise SystemExit(
                f"{calendar_name}: expected team "
                f"'{info['team']}' not found. "
                "Refusing to update calendar."
            )

        fixtures = extract_fixtures(
            page,
            info["team"],
            calendar_name,
        )

        if not fixtures:
            raise SystemExit(
                f"{calendar_name}: no fixtures found. "
                "Refusing to update calendar."
            )

        print(
            f"{calendar_name}: "
            f"{len(fixtures)} fixtures found"
        )

        all_events.extend(fixtures)

    current = CALENDAR.read_text(
        encoding="utf-8"
    )

    current = remove_fulltime_events(
        current
    )

    insert = (
        "\r\n".join(
            "\r\n".join(event)
            for event in all_events
        )
        + "\r\n"
    )

    if "END:VCALENDAR" not in current:
        raise SystemExit(
            "calendar.ics is not a valid calendar."
        )

    current = current.replace(
        "END:VCALENDAR",
        insert + "END:VCALENDAR",
    )

    CALENDAR.write_text(
        current,
        encoding="utf-8",
    )

    print()
    print(
        f"Full-Time events updated: "
        f"{len(all_events)}"
    )
    print(
        "Lucas calendar data was preserved."
    )


if __name__ == "__main__":
    main()