#!/usr/bin/env python3

from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re


# ============================================================
# SETTINGS
# ============================================================

FULLTIME_URL = (
    "https://paulcalvert81-dotcom.github.io/"
    "boys-sports-calendar/test_club_feed.html"
)

LRGS_URL = (
    "https://calendar.lrgs.org.uk/CalendarSync.ashx?"
    "Cal=Lancaster%20Royal%20Grammar%20School%20Calendar&"
    "ID=334&FT=OR&sid=71&sid=24&ST=0"
)

OUTPUT_LUCAS = Path("u14s-lrgs-rugby.ics")
OUTPUT_THOMAS = Path("u12-bluestars.ics")
OUTPUT_HARRY = Path("u9-bluestars.ics")
OUTPUT_COMBINED = Path("calendar.ics")


# ============================================================
# GENERAL ICS HELPERS
# ============================================================

def escape_ics(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def ics_event(
    uid,
    start,
    end,
    summary,
    location="",
    description=""
):
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;TZID=Europe/London:{start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID=Europe/London:{end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{escape_ics(summary)}",
    ]

    if location:
        lines.append(
            f"LOCATION:{escape_ics(location)}"
        )

    if description:
        lines.append(
            f"DESCRIPTION:{escape_ics(description)}"
        )

    lines.append("END:VEVENT")

    return lines


def create_calendar(events):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boys Sports Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for event in events:
        lines.extend(event)

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def write_calendar(path, events):
    path.write_text(
        create_calendar(events),
        encoding="utf-8"
    )

    print(
        f"Wrote {path}: {len(events)} events"
    )


# ============================================================
# FULL-TIME
# ============================================================

TARGET_TEAMS = {
    "Heysham Blue Star U9": "Harry",
    "Heysham Blue Star U12": "Thomas",
}


def parse_fulltime_date(text):
    text = " ".join(text.split())

    # Full-Time uses "Sept"; Python expects "Sep"
    text = re.sub(
        r"\bSept\b",
        "Sep",
        text
    )

    try:
        return datetime.strptime(
            text,
            "%a %d %b %Y %H:%M"
        )

    except ValueError:
        return None


def parse_fulltime_fixtures(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    table = soup.find("table")

    if not table:
        raise RuntimeError(
            "Full-Time fixture table not found"
        )

    fixtures = []

    current_datetime = None

    for row in table.find_all("tr"):

        cells = row.find_all("td")

        if not cells:
            continue

        # ----------------------------------------------------
        # DATE / TIME ROW
        # ----------------------------------------------------

        if len(cells) == 1:

            text = cells[0].get_text(
                " ",
                strip=True
            )

            parsed = parse_fulltime_date(text)

            if parsed:
                current_datetime = parsed

            continue

        if len(cells) < 4:
            continue

        cell_texts = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        # ----------------------------------------------------
        # HOME / AWAY
        # ----------------------------------------------------

        v_index = None

        for i, text in enumerate(cell_texts):

            if text.lower() == "v":

                v_index = i

                break

        if v_index is None:
            continue

        if (
            v_index < 1
            or
            v_index + 1 >= len(cell_texts)
        ):
            continue

        home = cell_texts[
            v_index - 1
        ]

        away = cell_texts[
            v_index + 1
        ]

        venue = ""

        if v_index + 2 < len(cell_texts):

            venue = cell_texts[
                v_index + 2
            ]

        # ----------------------------------------------------
        # COMPETITION
        # ----------------------------------------------------

        competition = ""

        for text in cell_texts:

            if text in {
                "CC",
                "ACUP"
            }:

                competition = text

                break

        # ----------------------------------------------------
        # FIXTURE ID
        # ----------------------------------------------------

        fixture_id = ""

        for link in row.find_all("a"):

            href = link.get(
                "href",
                ""
            )

            match = re.search(
                r"displayFixture\.html\?id=(\d+)",
                href
            )

            if match:

                fixture_id = match.group(1)

                break

        # ----------------------------------------------------
        # FIND BOY
        # ----------------------------------------------------

        boy = None
        target_team = None

        for team_name, boy_name in TARGET_TEAMS.items():

            if (
                home == team_name
                or
                away == team_name
            ):

                boy = boy_name
                target_team = team_name

                break

        if not boy:
            continue

        home_away = (
            "HOME"
            if home == target_team
            else "AWAY"
        )

        fixtures.append({
            "boy": boy,
            "fixture_id": fixture_id,
            "datetime": current_datetime,
            "home": home,
            "away": away,
            "venue": venue,
            "competition": competition,
            "home_away": home_away,
        })

    return fixtures


def get_fulltime_fixtures():

    print()
    print("Launching Chromium...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        print(
            "Opening Full-Time page:"
        )

        print(FULLTIME_URL)

        page.goto(
            FULLTIME_URL,
            wait_until="load",
            timeout=60000
        )

        print(
            "Waiting for Full-Time..."
        )

        page.wait_for_timeout(
            15000
        )

        print(
            "Waiting for fixture table..."
        )

        table = page.locator(
            "table"
        ).first

        table.wait_for(
            state="visible",
            timeout=30000
        )

        html = table.evaluate(
            "(element) => element.outerHTML"
        )

        print(
            "Fixture table captured:",
            len(html),
            "characters"
        )

        browser.close()

    fixtures = parse_fulltime_fixtures(
        html
    )

    if not fixtures:

        raise RuntimeError(
            "No Harry or Thomas fixtures found"
        )

    return fixtures


# ============================================================
# FULL-TIME → ICS
# ============================================================

def create_fulltime_events(fixtures):

    events = []

    for fixture in fixtures:

        start = fixture["datetime"]

        if not start:
            continue

        end = start + timedelta(
            minutes=90
        )

        boy = fixture["boy"]

        if boy == "Harry":

            feed_name = "U9 Bluestars"

        else:

            feed_name = "U12 Bluestars"

        # Clean title
        opponent = (
            fixture["away"]
            if fixture["home_away"] == "HOME"
            else fixture["home"]
        )

        summary = (
            f"{feed_name}: "
            f"{'HOME' if fixture['home_away'] == 'HOME' else 'AWAY'} "
            f"v {opponent}"
        )

        description_lines = [
            f"{fixture['home']} v {fixture['away']}"
        ]

        if fixture["competition"]:

            description_lines.append(
                f"Competition: "
                f"{fixture['competition']}"
            )

        description_lines.append(
            "Source: FA Full-Time"
        )

        # Prefer fixture ID as UID.
        # Fall back to date/teams for fixtures
        # where Full-Time provides no ID.

        if fixture["fixture_id"]:

            uid = (
                f"fulltime-{fixture['fixture_id']}"
                "@boys-sports-calendar"
            )

        else:

            key = (
                f"{start.strftime('%Y%m%d%H%M')}-"
                f"{fixture['home']}-"
                f"{fixture['away']}"
            )

            key = re.sub(
                r"[^a-zA-Z0-9]+",
                "-",
                key
            ).strip("-").lower()

            uid = (
                f"fulltime-{key}"
                "@boys-sports-calendar"
            )

        events.append(
            ics_event(
                uid=uid,
                start=start,
                end=end,
                summary=summary,
                location=fixture["venue"],
                description="\n".join(
                    description_lines
                ),
            )
        )

    return events


# ============================================================
# LUCAS / LRGS
# ============================================================

def get_prop(block, name):

    match = re.search(
        r"(?mi)^"
        + re.escape(name)
        + r"(?:;[^:]*)?:(.*)$",
        block
    )

    if not match:
        return ""

    value = match.group(1).strip()

    return (
        value
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def parse_lrgs_datetime(value):

    match = re.match(
        r"(\d{4})(\d{2})(\d{2})"
        r"T(\d{2})(\d{2})(\d{2})",
        value
    )

    if not match:
        return None

    return datetime(
        *map(
            int,
            match.groups()
        )
    )


def get_lucas_events():

    print()
    print(
        "Downloading Lucas LRGS feed..."
    )

    request = Request(
        LRGS_URL,
        headers={
            "User-Agent":
                "Boys-Sports-Calendar/1.0"
        }
    )

    with urlopen(
        request,
        timeout=30
    ) as response:

        remote = response.read().decode(
            "utf-8",
            errors="replace"
        )

    events = []

    for block in re.findall(
        r"BEGIN:VEVENT(.*?)END:VEVENT",
        remote,
        re.S
    ):

        summary = get_prop(
            block,
            "SUMMARY"
        )

        if "Boys-U14" not in summary:
            continue

        if not (
            summary.startswith(
                "Rugby Union "
            )
            or
            summary.startswith(
                "Rugby 7S "
            )
        ):
            continue

        squad = re.search(
            r"Boys-U14([A-Z])\b",
            summary
        )

        if squad and squad.group(1) not in {
            "A",
            "B"
        }:
            continue

        start_value = get_prop(
            block,
            "DTSTART"
        )

        start = parse_lrgs_datetime(
            start_value
        )

        if not start:
            continue

        location_status = get_prop(
            block,
            "LOCATION"
        )

        location_status = {
            "H": "Home",
            "A": "Away"
        }.get(
            location_status,
            location_status
        )

        clean = summary.replace(
            "Rugby Union Boys-U14",
            "U14"
        )

        clean = clean.replace(
            "Rugby 7S Boys-U14",
            "U14 7S"
        )

        clean = clean.replace(
            "UU14",
            "U14"
        )

        title = (
            f"U14s LRGS Rugby: "
            f"{clean}"
        )

        description = (
            "Source: LRGS Rugby"
        )

        if location_status:

            description += (
                f"\nVenue status: "
                f"{location_status}"
            )

        uid_key = re.sub(
            r"[^a-z0-9]+",
            "-",
            clean.lower()
        ).strip("-")

        uid = (
            f"lucas-"
            f"{start.strftime('%Y%m%d%H%M')}-"
            f"{uid_key}"
            "@boys-sports-calendar"
        )

        end = start + timedelta(
            minutes=90
        )

        events.append(
            ics_event(
                uid=uid,
                start=start,
                end=end,
                summary=title,
                description=description,
            )
        )

    if not events:

        raise RuntimeError(
            "No Lucas U14 Rugby events found"
        )

    print(
        f"Lucas events found: "
        f"{len(events)}"
    )

    return events


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BOYS SPORTS CALENDAR UPDATE")
    print("=" * 70)

    # --------------------------------------------------------
    # Get Full-Time
    # --------------------------------------------------------

    fulltime = get_fulltime_fixtures()

    print()
    print(
        f"Full-Time fixtures found: "
        f"{len(fulltime)}"
    )

    # --------------------------------------------------------
    # Split Harry / Thomas
    # --------------------------------------------------------

    harry_fixtures = [
        fixture
        for fixture in fulltime
        if fixture["boy"] == "Harry"
    ]

    thomas_fixtures = [
        fixture
        for fixture in fulltime
        if fixture["boy"] == "Thomas"
    ]

    # Safety checks
    if not harry_fixtures:

        raise RuntimeError(
            "No Harry U9 fixtures found. "
            "Refusing to overwrite calendars."
        )

    if not thomas_fixtures:

        raise RuntimeError(
            "No Thomas U12 fixtures found. "
            "Refusing to overwrite calendars."
        )

    # --------------------------------------------------------
    # Create events
    # --------------------------------------------------------

    harry_events = create_fulltime_events(
        harry_fixtures
    )

    thomas_events = create_fulltime_events(
        thomas_fixtures
    )

    lucas_events = get_lucas_events()

    # --------------------------------------------------------
    # Write individual calendars
    # --------------------------------------------------------

    write_calendar(
        OUTPUT_HARRY,
        harry_events
    )

    write_calendar(
        OUTPUT_THOMAS,
        thomas_events
    )

    write_calendar(
        OUTPUT_LUCAS,
        lucas_events
    )

    # --------------------------------------------------------
    # Combined calendar
    # --------------------------------------------------------

    combined = (
        lucas_events
        + thomas_events
        + harry_events
    )

    write_calendar(
        OUTPUT_COMBINED,
        combined
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("UPDATE COMPLETE")
    print("=" * 70)

    print(
        f"U14s LRGS Rugby : {len(lucas_events)}"
    )

    print(
        f"U12 Bluestars   : {len(thomas_events)}"
    )

    print(
        f"U9 Bluestars    : {len(harry_events)}"
    )

    print(
        f"Combined        : {len(combined)}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()