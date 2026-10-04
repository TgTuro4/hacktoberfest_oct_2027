"""Collector parsing against saved responses. No test touches the network."""

from datetime import datetime

from conftest import FIXTURES, fixture_json, fixture_text

from umd_events.collectors.athletics import AthleticsCollector
from umd_events.collectors.clarice import ClariceCollector, extract_calendar, extract_detail
from umd_events.collectors.civicplus import ics_to_records
from umd_events.collectors.college_park import CollegeParkCollector
from umd_events.collectors.pg_parks import PGParksCollector
from umd_events.collectors.recwell import RecWellCollector, extract_rows
from umd_events.collectors.see import SEECollector, extract_event_page
from umd_events.collectors.terplink import TerpLinkCollector
from umd_events.collectors.terps_after_dark import TerpsAfterDarkCollector, extract_cards
from umd_events.collectors.ticketmaster import TicketmasterCollector
from umd_events.collectors.umd_calendar import UMDCalendarCollector, extract_detail as umd_detail
from umd_events.pipeline import prepare


def parse_one(collector, source_event_id, data, url=None):
    return collector.parse(collector.raw(source_event_id, data, url))


def test_umd_calendar_detail_page():
    detail = umd_detail(fixture_text("umd_calendar_detail.html"))
    assert detail["venue"] == "The Clarice Smith Performing Arts Center"
    assert detail["address"] == "8270 Alumni Drive, College Park, MD 20742-1625"
    assert detail["ticket_url"] == "https://go.umd.edu/fy27-cc-cp-cr"
    assert "College of Arts and Humanities" in detail["hosts"]


def test_umd_calendar_parse(settings):
    collector = UMDCalendarCollector(None, settings)
    records = {r["id"]: r for r in fixture_json("umd_calendar_events.json")}
    detail = umd_detail(fixture_text("umd_calendar_detail.html"))

    [event] = parse_one(collector, "454281:x", {**records[454281], "_detail": detail})
    assert event.title == "Counterpoint: Rhapsody in Blue ft. Conrad Tao & Caleb Teicher"
    # GraphQL says 15:00+00:00 but means 3pm Eastern
    assert event.start_time.isoformat() == "2026-10-04T15:00:00-04:00"
    assert event.venue_name == "The Clarice Smith Performing Arts Center"
    assert event.source_url.endswith("?start=2026-10-04")
    assert event.organizer_name == "College of Arts and Humanities"
    assert event.registration_url == "https://go.umd.edu/fy27-cc-cp-cr"
    prepared = prepare(event)
    assert prepared.venue_id == "clarice-smith-center"
    assert {"concert", "dance"} <= set(prepared.tags)

    # Recurring occurrence whose end is reported as the end of the series gets clamped to the same day.
    [flower] = parse_one(collector, "455460:x", {**records[455460], "_detail": {}})
    assert flower.end_time.date() == flower.start_time.date()
    assert flower.end_time.hour == 15


def test_terplink_parse(settings):
    collector = TerpLinkCollector(None, settings)
    record = fixture_json("terplink_search.json")["value"][1]
    [event] = parse_one(collector, record["id"], record)
    assert event.title == "Wiggle Room Workshop"
    assert event.start_time.isoformat() == "2026-10-04T17:00:00-04:00"  # 21:00 UTC
    assert event.organizer_name == "Maryland Manzar"
    assert event.source_url == "https://terplink.umd.edu/event/12663723"
    assert event.image_url.startswith("https://se-images.campuslabs.com/clink/images/")
    assert event.external_refs == {"terplink": "12663723"}
    prepared = prepare(event)
    assert prepared.venue_id == "stamp-student-union"
    assert "workshop" in prepared.tags and "student_organization" in prepared.tags


def test_terplink_building_code(settings):
    collector = TerpLinkCollector(None, settings)
    record = fixture_json("terplink_search.json")["value"][0]  # location "ASY Art-Socy 3207"
    prepared = prepare(parse_one(collector, record["id"], record)[0])
    assert prepared.venue_id == "umd-art-sociology-building"
    assert prepared.event_type == "meeting"


def test_athletics_home_games_only(settings):
    collector = AthleticsCollector(None, settings)
    events = [e for day in fixture_json("athletics_month.json") for e in day["events"]]
    parsed = [ev for e in events for ev in parse_one(collector, e["id"], e)]
    assert [e.title for e in parsed] == ["Maryland Women's Soccer vs UCLA", "Maryland Football vs Ohio State"]
    soccer, football = parsed
    assert soccer.start_time.isoformat() == "2026-10-11T12:00:00-04:00"
    assert soccer.venue_name == "Ludwig Field"
    assert soccer.registration_url.startswith("https://umterps.evenue.net/event/WS26/WS07")
    assert "utm_source" not in soccer.registration_url
    assert soccer.extra["opponent"] == "#12 UCLA"
    assert football.all_day  # time TBA
    assert prepare(football).venue_id == "secu-stadium"


def test_clarice(settings):
    occurrences, next_url = extract_calendar(fixture_text("clarice_calendar.html"))
    assert occurrences[0]["url"] == "https://theclarice.umd.edu/events/leslie-jones"
    assert occurrences[0]["date"] == "2026-10-07"
    assert next_url and "calendar_timestamp=" in next_url

    detail = extract_detail(fixture_text("clarice_detail.html"))
    assert detail["title"] == "Leslie Jones"
    collector = ClariceCollector(None, settings)
    [event] = parse_one(collector, "leslie-jones",
                        {"url": occurrences[0]["url"], "occurrences": occurrences, "detail": detail})
    assert event.start_time.isoformat() == "2026-10-07T20:00:00-04:00"
    assert event.venue_name.startswith("Dekelboum Concert Hall")
    assert (event.price_min, event.price_max, event.is_free) == (20.0, 75.0, False)  # booking fee ignored
    assert "comedy" in prepare(event).tags


def test_college_park_ics(settings):
    collector = CollegeParkCollector(None, settings)
    records = ics_to_records((FIXTURES / "college_park_calendar.ics").read_bytes(), "City Events")
    events = {e.title: e for r in records for e in parse_one(collector, r["uid"], {**r, "categories": ["City Events"]})}
    rave = events["Rave at the Grave"]
    assert rave.start_time.isoformat() == "2026-10-23T18:00:00-04:00"
    assert rave.venue_name == "Duvall Field"
    assert rave.address == "9100 Rhode Island Avenue College Park MD 20740"
    assert rave.source_url == "https://www.collegeparkmd.gov/Calendar.aspx?EID=10272"
    prepared = prepare(rave)
    assert prepared.venue_id == "duvall-field" and prepared.latitude
    assert {"community", "nightlife"} <= set(prepared.tags)


def test_terps_after_dark_cards(settings):
    cards = extract_cards(fixture_text("terps_after_dark.html"))
    bingo = next(c for c in cards if "Bingo" in c["title"])
    assert bingo["terplink_id"] == "12757562"
    assert bingo["presenter"] == "STAMP Programs"
    collector = TerpsAfterDarkCollector(None, settings)
    [event] = parse_one(collector, bingo["terplink_id"], {"kind": "card", **bingo})
    assert event.start_time.hour == 19 and event.end_time.hour == 21
    assert event.venue_name == "the Baltimore Room of STAMP"
    assert prepare(event).venue_id == "stamp-student-union"
    assert {"nightlife", "social"} <= set(event.tags)


def test_see_event_page(settings):
    page = extract_event_page(fixture_text("see_event_page.html"), "https://www.see.umd.edu/homecoming-comedy-show-2026")
    collector = SEECollector(None, settings)
    [event] = parse_one(collector, "site:homecoming", {"kind": "site", **page})
    assert event.title == "Homecoming Comedy Show"
    assert event.start_time.isoformat() == "2026-10-15T20:00:00-04:00"
    assert event.venue_name == "XFINITY Center"
    assert (event.price_min, event.price_max) == (20.0, 50.0)
    prepared = prepare(event)
    assert prepared.venue_id == "xfinity-center"
    assert "comedy" in prepared.tags


def test_recwell_intramurals(settings):
    rows = extract_rows(fixture_text("recwell_intramurals.html"))
    volleyball = next(r for r in rows if r["sport"] == "4v4 Volleyball")
    collector = RecWellCollector(None, settings)
    collector.now = datetime.fromisoformat("2026-10-04T12:00:00-04:00")
    events = {e.event_type: e for e in parse_one(collector, "4v4-volleyball", volleyball)}
    assert events["registration_deadline"].start_time.date().isoformat() == "2026-10-07"
    assert events["activity"].title == "Intramural 4v4 Volleyball: Play Begins"
    assert set(events) == {"registration_open", "registration_deadline", "activity"}


def test_pg_parks(settings):
    collector = PGParksCollector(None, settings)
    free, paid = [parse_one(collector, e["id"], {**e, "_facility_tag": "college-park-aviation-museum"})[0]
                  for e in fixture_json("pg_parks_events.json")["events"]]
    assert free.start_time.isoformat() == "2026-10-10T11:00:00-04:00"
    assert free.is_free is True and free.venue_name == "College Park Aviation Museum"
    assert (paid.price_min, paid.price_max, paid.is_free) == (4.0, 6.0, False)
    assert "outdoors" in prepare(paid).tags


def test_ticketmaster(settings):
    collector = TicketmasterCollector(None, settings)
    concert, cancelled = fixture_json("ticketmaster_events.json")["_embedded"]["events"]
    [event] = parse_one(collector, concert["id"], concert)
    assert event.start_time.isoformat() == "2026-11-06T20:00:00-05:00"
    assert event.image_url.endswith("large.jpg")
    assert (event.price_min, event.price_max) == (35.0, 89.5)
    assert {"concert", "music"} <= set(prepare(event).tags)
    assert parse_one(collector, cancelled["id"], cancelled) == []
    assert collector.skip_reason()  # no API key configured in tests
