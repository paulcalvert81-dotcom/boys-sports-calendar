#!/usr/bin/env python3
"""
BOYS SPORTS CALENDAR v5

Reads boys_sports_fixtures.csv and creates a clean combined ICS calendar.

Fixes from v4:
- Corrects Lucas "UU14A/UU14B" to "U14A/U14B".
- Shows LRGS H/A as Home/Away.
- Keeps U14A and U14B as separate events.
- Supports Rugby Union and Rugby 7S events already present in the source CSV.
"""

import csv
from pathlib import Path
from datetime import datetime, timedelta, timezone

INPUT = Path("boys_sports_fixtures.csv")
OUTPUT = Path("boys_sports_calendar_v5.ics")


def escape_ics(value):
    if value is None:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def clean_lucas_summary(summary):
    """Turn the raw LRGS summary into a clean display title."""
    text = summary.strip()

    text = text.replace(
        "Rugby Union Boys-U14",
        "U14"
    )
    text = text.replace(
        "Rugby 7S Boys-U14",
        "U14 7S"
    )

    # Safety net for the exact v4 typo if it ever appears in the CSV.
    text = text.replace("UU14", "U14")

    return text


def make_title(row):
    boy = row["boy"].strip()

    if boy == "Lucas":
        return f"Lucas Rugby: {clean_lucas_summary(row['away'])}"

    return (
        f'{boy} Football: '
        f'{row["home"].strip()} v {row["away"].strip()}'
    )


def make_location(row):
    if row["boy"].strip() != "Lucas":
        return row.get("venue", "").strip()

    value = row.get("venue", "").strip()

    if value == "H":
        return "Home"

    if value == "A":
        return "Away"

    return value


def make_description(row, location):
    parts = []

    competition = row.get("competition", "").strip()
    source = row.get("source", "").strip()
    status = row.get("status", "").strip()

    if competition:
        parts.append(f"Competition: {competition}")

    if source:
        parts.append(f"Source: {source}")

    if location and row["boy"].strip() == "Lucas":
        parts.append(f"Venue status: {location}")

    if status:
        parts.append(f"Status: {status}")

    return "\n".join(parts)


def main():
    print("==========================================")
    print("       BOYS SPORTS CALENDAR v5")
    print("==========================================")

    if not INPUT.exists():
        print()
        print(f"ERROR: {INPUT} was not found.")
        print("Run py boys_sports_v2.py first.")
        print()
        return

    with INPUT.open(
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as f:
        rows = list(csv.DictReader(f))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boys Sports Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Boys Sports",
        "X-WR-TIMEZONE:Europe/London",
    ]

    written = 0

    for number, row in enumerate(rows, start=1):
        try:
            start = datetime.strptime(
                f'{row["date"]} {row["time"]}',
                "%d/%m/%y %H:%M"
            )
        except (ValueError, KeyError):
            print(
                f'WARNING: skipping invalid row {number}: '
                f'{row.get("date", "")} {row.get("time", "")}'
            )
            continue

        end = start + timedelta(minutes=90)

        title = make_title(row)
        location = make_location(row)
        description = make_description(row, location)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        uid = (
            f'boys-sports-{row["boy"].strip().lower()}-'
            f'{start.strftime("%Y%m%d%H%M")}-{number}'
            f'@boys-sports-calendar'
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f'DTSTART;TZID=Europe/London:{start.strftime("%Y%m%dT%H%M%S")}',
            f'DTEND;TZID=Europe/London:{end.strftime("%Y%m%dT%H%M%S")}',
            f"SUMMARY:{escape_ics(title)}",
        ])

        if location:
            lines.append(f"LOCATION:{escape_ics(location)}")

        if description:
            lines.append(
                f"DESCRIPTION:{escape_ics(description)}"
            )

        lines.append("END:VEVENT")
        written += 1

    lines.append("END:VCALENDAR")

    OUTPUT.write_text(
        "\r\n".join(lines) + "\r\n",
        encoding="utf-8"
    )

    print(f"Fixtures read: {len(rows)}")
    print(f"Events written: {written}")
    print(f"Calendar created: {OUTPUT.name}")
    print()
    print("Lucas U14 titles cleaned.")
    print("Lucas H/A converted to Home/Away.")
    print("==========================================")


if __name__ == "__main__":
    main()
