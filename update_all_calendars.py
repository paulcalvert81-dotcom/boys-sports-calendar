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
# ICS HELPERS
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


def ics_event(uid, start, end, summary, location="", description=""):

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


def create_calendar(events, calendar_name, description=""):

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boys Sports Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",

        # ----------------------------------------------------
        # Proper calendar name
        # ----------------------------------------------------

        f"X-WR-CALNAME:{escape_ics(calendar_name)}",

        # ----------------------------------------------------
        # Description shown by some calendar apps
        # ----------------------------------------------------

        f"X-WR-CALDESC:{escape_ics(description)}",

        # ----------------------------------------------------
        # Calendar timezone
        # ----------------------------------------------------

        "X-WR-TIMEZONE:Europe/London",
    ]

    for event in events:
        lines.extend(event)

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def write_calendar(path, events, calendar_name, description=""):

    path.write_text(
        create_calendar(
            events,
            calendar_name,
            description
        ),
        encoding="utf-8"
    )

    print(
        f"Wrote {path}: "
        f"{len(events)} events "
        f"({calendar_name})"
    )


# ============================================================
# FULL-TIME DATE PARSING
# ============================================================

def parse_fulltime_date(text):

    text = " ".join(text.split())

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


# ============================================================
# FULL-TIME HTML PARSER
# ============================================================

TARGET_TEAMS = {
    "Heysham Blue Star U9": "Harry",
    "Heysham Blue Star U12": "Thomas",
}


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
        # FIND "v"
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
        # IDENTIFY HARRY / THOMAS
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


# ============================================================
# FULL-TIME BROWSER
# ============================================================

def get_fulltime_fixtures():

    print()
    print("=" * 70)
    print("FULL-TIME BROWSER")
    print("=" * 70)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page(
            viewport={
                "width": 1280,
                "height": 1000
            }
        )

        page.set_default_timeout(
            10000
        )

        print()
        print("Opening:")
        print(FULLTIME_URL)

        page.goto(
            FULLTIME_URL,
            wait_until="load",
            timeout=60000
        )

        print(
            "Initial page load complete."
        )

        # ----------------------------------------------------
        # Poll for Full-Time data
        # ----------------------------------------------------

        found = False

        for attempt in range(1, 13):

            print(
                f"Waiting for Full-Time data "
                f"(attempt {attempt}/12)..."
            )

            page.wait_for_timeout(
                5000
            )

            body_text = page.locator(
                "body"
            ).inner_text(
                timeout=10000
            )

            table_count = page.locator(
                "table"
            ).count()

            print(
                f"  tables in DOM: {table_count}"
            )

            print(
                f"  page text length: "
                f"{len(body_text)}"
            )

            if (
                "Heysham Blue Star U12"
                in body_text
                or
                "Heysham Blue Star U9"
                in body_text
            ):

                print(
                    "  Full-Time fixture text found."
                )

                found = True
                break

        # ----------------------------------------------------
        # Reload if necessary
        # ----------------------------------------------------

        if not found:

            print()
            print(
                "Full-Time did not appear."
            )

            print(
                "Reloading page and trying again..."
            )

            page.reload(
                wait_until="load",
                timeout=60000
            )

            for attempt in range(1, 7):

                print(
                    f"Retry {attempt}/6..."
                )

                page.wait_for_timeout(
                    5000
                )

                body_text = page.locator(
                    "body"
                ).inner_text(
                    timeout=10000
                )

                if (
                    "Heysham Blue Star U12"
                    in body_text
                    or
                    "Heysham Blue Star U9"
                    in body_text
                ):

                    print(
                        "Full-Time fixture text found "
                        "after reload."
                    )

                    found = True
                    break

        # ----------------------------------------------------
        # Diagnostics if failed
        # ----------------------------------------------------

        if not found:

            print(
                "ERROR: Full-Time did not load."
            )

            page.screenshot(
                path="fulltime-failure.png",
                full_page=True
            )

            Path(
                "fulltime-failure.txt"
            ).write_text(
                page.locator(
                    "body"
                ).inner_text(
                    timeout=10000
                ),
                encoding="utf-8"
            )

            browser.close()

            raise RuntimeError(
                "Full-Time fixture data did not load"
            )

        # ----------------------------------------------------
        # Find table
        # ----------------------------------------------------

        print()
        print(
            "Waiting for fixture table..."
        )

        page.locator(
            "table"
        ).first.wait_for(
            state="attached",
            timeout=30000
        )

        print(
            "Fixture table attached."
        )

        tables = page.locator(
            "table"
        )

        best_html = ""

        for i in range(
            tables.count()
        ):

            try:

                html = tables.nth(i).evaluate(
                    "(element) => element.outerHTML"
                )

                if len(html) > len(
                    best_html
                ):

                    best_html = html

            except Exception:
                pass

        if not best_html:

            page.screenshot(
                path="fulltime-failure.png",
                full_page=True
            )

            browser.close()

            raise RuntimeError(
                "Full-Time table exists but "
                "could not be captured"
            )

        print(
            "Captured fixture table:",
            len(best_html),
            "characters"
        )

        page.screenshot(
            path="fulltime-production.png",
            full_page=True
        )

        browser.close()

    # --------------------------------------------------------
    # Parse table
    # --------------------------------------------------------

    fixtures = parse_fulltime_fixtures(
        best_html
    )

    if not fixtures:

        raise RuntimeError(
            "Full-Time table captured but "
            "no Harry or Thomas fixtures found"
        )

    print()
    print(
        f"Harry + Thomas fixtures found: "
        f"{len(fixtures)}"
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

        opponent = (
            fixture["away"]
            if fixture["home_away"] == "HOME"
            else fixture["home"]
        )

        home_away = fixture["home_away"]

        summary = (
            f"{home_away} v {opponent}"
        )

        description_lines = [
            f"{fixture['home']} v "
            f"{fixture['away']}"
        ]

        if fixture["competition"]:

            description_lines.append(
                f"Competition: "
                f"{fixture['competition']}"
            )

        description_lines.append(
            "Source: FA Full-Time"
        )

        # ----------------------------------------------------
        # Stable UID
        # ----------------------------------------------------

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
# LRGS / LUCAS
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
    print("=" * 70)
    print("LUCAS / LRGS")
    print("=" * 70)

    print(
        "Downloading LRGS feed..."
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

        title = clean

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
    # Full-Time
    # --------------------------------------------------------

    fulltime = get_fulltime_fixtures()

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

    # --------------------------------------------------------
    # Safety checks
    # --------------------------------------------------------

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
    # Write individual feeds
    # --------------------------------------------------------

    write_calendar(
        OUTPUT_LUCAS,
        lucas_events,
        "U14s LRGS Rugby",
        "Lucas U14 rugby fixtures from LRGS"
    )

    write_calendar(
        OUTPUT_THOMAS,
        thomas_events,
        "U12 Bluestars",
        "Thomas U12 Heysham Blue Star fixtures"
    )

    write_calendar(
        OUTPUT_HARRY,
        harry_events,
        "U9 Bluestars",
        "Harry U9 Heysham Blue Star fixtures"
    )

    # --------------------------------------------------------
    # Combined personal feed
    # --------------------------------------------------------

    combined = (
        lucas_events
        + thomas_events
        + harry_events
    )

    write_calendar(
        OUTPUT_COMBINED,
        combined,
        "Boys Sports Calendar",
        "Lucas, Thomas and Harry sports fixtures"
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("UPDATE COMPLETE")
    print("=" * 70)

    print(
        f"U14s LRGS Rugby : "
        f"{len(lucas_events)}"
    )

    print(
        f"U12 Bluestars   : "
        f"{len(thomas_events)}"
    )

    print(
        f"U9 Bluestars    : "
        f"{len(harry_events)}"
    )

    print(
        f"Combined        : "
        f"{len(combined)}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()