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


def ics_timed_event(
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


def ics_allday_event(
    uid,
    date_value,
    summary,
    location="",
    description=""
):
    next_day = date_value + timedelta(days=1)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{date_value.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}",
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


def create_calendar(
    events,
    calendar_name,
    description=""
):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boys Sports Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics(calendar_name)}",
        f"X-WR-CALDESC:{escape_ics(description)}",
        "X-WR-TIMEZONE:Europe/London",
    ]

    for event in events:
        lines.extend(event)

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def write_calendar(
    path,
    events,
    calendar_name,
    description=""
):
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
        f"{len(events)} events ({calendar_name})"
    )


# ============================================================
# FULL-TIME
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

        if len(cells) == 1:

            text = cells[0].get_text(
                " ",
                strip=True
            )

            parsed = parse_fulltime_date(
                text
            )

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

        v_index = None

        for i, text in enumerate(
            cell_texts
        ):

            if text.lower() == "v":
                v_index = i
                break

        if v_index is None:
            continue

        if v_index < 1:
            continue

        if v_index + 1 >= len(
            cell_texts
        ):
            continue

        home = cell_texts[
            v_index - 1
        ]

        away = cell_texts[
            v_index + 1
        ]

        venue = ""

        if v_index + 2 < len(
            cell_texts
        ):
            venue = cell_texts[
                v_index + 2
            ]

        competition = ""

        for text in cell_texts:

            if text in {
                "CC",
                "ACUP"
            }:
                competition = text
                break

        fixture_id = ""

        for link in row.find_all(
            "a"
        ):

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

        boy = None
        target_team = None

        for team_name, boy_name in (
            TARGET_TEAMS.items()
        ):

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
    print("=" * 70)
    print("FULL-TIME BROWSER")
    print("=" * 70)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1280,
                "height": 1200
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0 Safari/537.36"
            )
        )

        page = context.new_page()

        page.set_default_timeout(
            15000
        )

        print()
        print("Opening:")
        print(FULLTIME_URL)

        try:

            page.goto(
                FULLTIME_URL,
                wait_until="domcontentloaded",
                timeout=90000
            )

        except Exception as e:

            print(
                "Initial navigation warning:",
                e
            )

        print(
            "Initial page navigation complete."
        )

        found = False

        for attempt in range(
            1,
            25
        ):

            print(
                f"Checking Full-Time "
                f"(attempt {attempt}/24)..."
            )

            try:

                body_text = page.locator(
                    "body"
                ).inner_text(
                    timeout=15000
                )

            except Exception:

                body_text = ""

            table_count = page.locator(
                "table"
            ).count()

            print(
                f"  Tables: {table_count}"
            )

            print(
                f"  Text length: "
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
                    "  Full-Time fixture "
                    "data found."
                )

                found = True
                break

            page.wait_for_timeout(
                5000
            )

        if not found:

            print(
                "Full-Time has not loaded."
            )

            try:

                page.reload(
                    wait_until="domcontentloaded",
                    timeout=90000
                )

            except Exception as e:

                print(
                    "Reload warning:",
                    e
                )

            for attempt in range(
                1,
                13
            ):

                print(
                    f"Reload attempt "
                    f"{attempt}/12..."
                )

                page.wait_for_timeout(
                    5000
                )

                try:

                    body_text = page.locator(
                        "body"
                    ).inner_text(
                        timeout=15000
                    )

                except Exception:

                    body_text = ""

                table_count = page.locator(
                    "table"
                ).count()

                print(
                    f"  Tables: {table_count} "
                    f"Text: {len(body_text)}"
                )

                if (
                    "Heysham Blue Star U12"
                    in body_text
                    or
                    "Heysham Blue Star U9"
                    in body_text
                ):

                    print(
                        "  Full-Time data found "
                        "after reload."
                    )

                    found = True
                    break

        if not found:

            browser.close()

            raise RuntimeError(
                "Full-Time fixture data "
                "did not load"
            )

        print()
        print(
            "Fixture data found."
        )

        print(
            "Looking for fixture table..."
        )

        best_html = ""

        for attempt in range(
            1,
            13
        ):

            tables = page.locator(
                "table"
            )

            count = tables.count()

            print(
                f"Table scan {attempt}/12: "
                f"{count} table(s)"
            )

            for i in range(count):

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

            if len(best_html) > 5000:

                print(
                    "Usable fixture table "
                    "captured."
                )

                break

            page.wait_for_timeout(
                2500
            )

        if not best_html:

            browser.close()

            raise RuntimeError(
                "Full-Time table "
                "could not be captured"
            )

        print(
            "Captured fixture table:",
            len(best_html),
            "characters"
        )

        browser.close()

    fixtures = parse_fulltime_fixtures(
        best_html
    )

    if not fixtures:

        raise RuntimeError(
            "No Harry or Thomas "
            "fixtures found"
        )

    print()
    print(
        f"Harry + Thomas fixtures found: "
        f"{len(fixtures)}"
    )

    return fixtures


def create_fulltime_events(
    fixtures
):

    events = []

    for fixture in fixtures:

        start = fixture["datetime"]

        if not start:
            continue

        end = start + timedelta(
            minutes=90
        )

        home_away = fixture[
            "home_away"
        ]

        opponent = (
            fixture["away"]
            if home_away == "HOME"
            else fixture["home"]
        )

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

        if fixture["fixture_id"]:

            uid = (
                f"fulltime-"
                f"{fixture['fixture_id']}"
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
            ics_timed_event(
                uid,
                start,
                end,
                summary,
                fixture["venue"],
                "\n".join(
                    description_lines
                )
            )
        )

    return events


# ============================================================
# LRGS HELPERS
# ============================================================

def unfold_ics(text):

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    return re.sub(
        r"\n[ \t]",
        "",
        text
    )


def get_prop(
    block,
    name
):

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


def parse_lrgs_datetime(
    value
):

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


# ============================================================
# LRGS / LUCAS
# ============================================================

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

    remote = unfold_ics(
        remote
    )

    # --------------------------------------------------------
    # Find EVERY U14 rugby event.
    # Nothing is filtered based on opponent name.
    # --------------------------------------------------------

    source_u14 = []

    for block in re.findall(
        r"BEGIN:VEVENT(.*?)END:VEVENT",
        remote,
        re.S
    ):

        summary = get_prop(
            block,
            "SUMMARY"
        )

        summary_lower = (
            summary.lower()
        )

        if "u14" not in summary_lower:
            continue

        is_rugby = (
            "rugby union"
            in summary_lower
            or
            "rugby 7s"
            in summary_lower
        )

        if not is_rugby:
            continue

        start_value = get_prop(
            block,
            "DTSTART"
        )

        start = parse_lrgs_datetime(
            start_value
        )

        if not start:

            raise RuntimeError(
                "LRGS contains a U14 Rugby "
                "event with an unreadable "
                f"DTSTART:\n{summary}"
            )

        source_u14.append({
            "block": block,
            "summary": summary,
            "start": start,
        })

    source_count = len(
        source_u14
    )

    print()
    print(
        f"LRGS U14 rugby events found: "
        f"{source_count}"
    )

    # --------------------------------------------------------
    # Convert EVERY source event.
    # --------------------------------------------------------

    events = []
    fixture_info = []

    for source_event in source_u14:

        block = source_event[
            "block"
        ]

        summary = source_event[
            "summary"
        ]

        start = source_event[
            "start"
        ]

        summary_lower = (
            summary.lower()
        )

        # ----------------------------------------------------
        # Clean the LRGS title
        # ----------------------------------------------------

        clean = summary

        replacements = [
            (
                "Rugby Union Boys-U14A",
                "U14A"
            ),
            (
                "Rugby Union Boys-U14B",
                "U14B"
            ),
            (
                "Rugby Union Boys-U14",
                "U14"
            ),
            (
                "Rugby 7S Boys-U14A",
                "U14A 7S"
            ),
            (
                "Rugby 7S Boys-U14B",
                "U14B 7S"
            ),
            (
                "Rugby 7S Boys-U14",
                "U14 7S"
            ),
        ]

        for old, new in replacements:

            clean = clean.replace(
                old,
                new
            )

        clean = clean.replace(
            "UU14",
            "U14"
        )

        clean = " ".join(
            clean.split()
        )

        # ----------------------------------------------------
        # HOME / AWAY
        # ----------------------------------------------------

        location_status = get_prop(
            block,
            "LOCATION"
        )

        location_status = {
            "H": "HOME",
            "A": "AWAY"
        }.get(
            location_status,
            location_status.upper()
            if location_status
            else ""
        )

        # ----------------------------------------------------
        # TBC / holding event
        # ----------------------------------------------------

        is_zero_time = (
            start.hour == 0
            and
            start.minute == 0
            and
            start.second == 0
        )

        is_tbc = (
            "tbc" in summary_lower
            or
            "to be confirmed"
            in summary_lower
            or
            is_zero_time
        )

        if is_tbc:

            if "timings tbc" not in clean.lower():

                clean = (
                    clean
                    + " (Timings TBC)"
                )

        # ----------------------------------------------------
        # Put HOME / AWAY INTO THE TITLE
        # ----------------------------------------------------

        if location_status in {
            "HOME",
            "AWAY"
        }:

            title = (
                f"{location_status} - {clean}"
            )

        else:

            title = clean

        # ----------------------------------------------------
        # Description
        # ----------------------------------------------------

        description = (
            "Source: LRGS Rugby"
        )

        if is_tbc:

            description += (
                "\nTiming: TBC"
                "\nHolding event - "
                "time to be confirmed"
            )

        if location_status:

            description += (
                f"\nVenue status: "
                f"{location_status.title()}"
            )

        # ----------------------------------------------------
        # Stable UID
        # ----------------------------------------------------

        source_uid = get_prop(
            block,
            "UID"
        )

        if source_uid:

            uid_key = re.sub(
                r"[^a-zA-Z0-9]+",
                "-",
                source_uid
            ).strip("-").lower()

        else:

            uid_key = re.sub(
                r"[^a-zA-Z0-9]+",
                "-",
                (
                    f"{start.strftime('%Y%m%d%H%M%S')}-"
                    f"{summary}"
                )
            ).strip("-").lower()

        uid = (
            f"lucas-{uid_key}"
            "@boys-sports-calendar"
        )

        # ----------------------------------------------------
        # Create event
        # ----------------------------------------------------

        if is_tbc:

            event = ics_allday_event(
                uid=uid,
                date_value=start.date(),
                summary=title,
                description=description
            )

            display_time = (
                f"{start.strftime('%d/%m/%Y')} "
                f"ALL DAY / TBC"
            )

        else:

            end = start + timedelta(
                minutes=90
            )

            event = ics_timed_event(
                uid=uid,
                start=start,
                end=end,
                summary=title,
                description=description
            )

            display_time = start.strftime(
                "%d/%m/%Y %H:%M"
            )

        events.append(
            event
        )

        fixture_info.append({
            "start": start,
            "title": title,
            "location": location_status,
            "display_time": display_time,
        })

    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    imported_count = len(
        events
    )

    skipped_count = (
        source_count
        - imported_count
    )

    print()
    print(
        f"LRGS U14 events to import: "
        f"{imported_count}"
    )

    print(
        f"LRGS U14 events skipped: "
        f"{skipped_count}"
    )

    if imported_count != source_count:

        print()
        print("=" * 70)
        print(
            "ERROR: LRGS U14 EVENT COUNT MISMATCH"
        )
        print("=" * 70)

        print(
            f"Source contains: "
            f"{source_count}"
        )

        print(
            f"Importer produced: "
            f"{imported_count}"
        )

        print(
            "Calendar files will NOT be written."
        )

        print("=" * 70)

        raise RuntimeError(
            "LRGS U14 event count mismatch"
        )

    # --------------------------------------------------------
    # Display fixtures
    # --------------------------------------------------------

    fixture_info.sort(
        key=lambda x: x["start"]
    )

    print()
    print("=" * 70)
    print("LUCAS U14 RUGBY FIXTURES")
    print("=" * 70)

    for number, fixture in enumerate(
        fixture_info,
        start=1
    ):

        print(
            f"{number:02d}. "
            f"{fixture['display_time']}  "
            f"{fixture['title']}"
        )

        if fixture["location"]:

            print(
                f"    Venue status: "
                f"{fixture['location'].title()}"
            )

    print("=" * 70)

    print(
        f"Lucas events found: "
        f"{len(events)}"
    )

    print("=" * 70)

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

    if not harry_fixtures:

        raise RuntimeError(
            "No Harry U9 fixtures found. "
            "Refusing to update calendars."
        )

    if not thomas_fixtures:

        raise RuntimeError(
            "No Thomas U12 fixtures found. "
            "Refusing to update calendars."
        )

    harry_events = create_fulltime_events(
        harry_fixtures
    )

    thomas_events = create_fulltime_events(
        thomas_fixtures
    )

    # --------------------------------------------------------
    # LRGS
    # --------------------------------------------------------

    lucas_events = get_lucas_events()

    # --------------------------------------------------------
    # INDIVIDUAL CALENDARS
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
    # COMBINED CALENDAR
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
    # FINAL SUMMARY
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