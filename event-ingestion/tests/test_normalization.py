from datetime import date, datetime, time

from umd_events.enrich.tagging import rule_tags
from umd_events.models import Event
from umd_events.normalize.prices import format_price, parse_price
from umd_events.normalize.text import html_to_text, summarize
from umd_events.normalize.times import find_date, infer_year, parse_floating, parse_time_range
from umd_events.normalize.titles import normalize_title
from umd_events.normalize.urls import clean_url
from umd_events.normalize.venues import venue_index


def test_normalize_title():
    assert normalize_title("SEE Presents: Spider-Man: Across the Spider-Verse") == "spider man across the spider verse"
    assert normalize_title("Terps After Dark: Plant Bingo") == "plant bingo"
    assert normalize_title("Maryland Women's Soccer vs #12 UCLA") == "maryland womens soccer vs ucla"
    assert normalize_title("Café Night (Rescheduled)") == "cafe night"


def test_venue_aliases_resolve_to_one_building():
    index = venue_index()
    ids = {index.resolve(name).venue_id for name in
           ["Hoff Theater", "Hoff Theatre", "Hoff Theater, Stamp", "The Stamp - Benjamin Banneker 2212"]}
    assert ids == {"stamp-student-union"}
    assert index.resolve("Comcast Center").venue_id == "xfinity-center"
    assert index.resolve("ESJ 0202").venue_id == "umd-edward-st-john-learning-and-teaching-center"
    assert index.resolve("Somewhere in Baltimore") is None
    assert index.resolve("Jimenez 2120").canonical_name == "Jimenez Hall"
    assert index.resolve("William E. Kirwan Hall (MTH 0104)").canonical_name == "Mathematics Building"
    assert index.resolve("Armory 0126").canonical_name == "Reckord Armory"
    assert index.resolve("the TerpZone").venue_id == "stamp-student-union"


def test_civicplus_location_split():
    from umd_events.collectors.civicplus import split_location

    assert split_location("City Facilities > City Hall Plaza - 7401 Baltimore Avenue  College Park MD 20740") == (
        "City Hall Plaza", "7401 Baltimore Avenue College Park MD 20740")
    assert split_location(" - Art Works Now 4800 Rhode Island Ave Hyattsville MD 20781") == (
        "Art Works Now", "4800 Rhode Island Ave Hyattsville MD 20781")
    assert split_location(" -   Hyattsville MD 20781") == (None, "Hyattsville MD 20781")


def test_times():
    assert parse_floating("2026-10-04T15:00:00+00:00").isoformat() == "2026-10-04T15:00:00-04:00"
    assert parse_time_range("7 to 9 p.m. in the Baltimore Room") == (time(19), time(21))
    assert parse_time_range("10:30am - 12pm") == (time(10, 30), time(12))
    assert parse_time_range("11 to 1 p.m.") == (time(11), time(13))
    assert find_date("Thursday, October 15th, 2026") == date(2026, 10, 15)
    assert infer_year(1, 10, reference=date(2026, 12, 1)) == date(2027, 1, 10)


def test_prices():
    assert parse_price("$45/$60/$75 + $5 booking fee Students: $20/$30") == (20.0, 75.0, False)
    assert parse_price("Free of Charge") == (0.0, 0.0, True)
    assert parse_price("Free for students, $10 general") == (0.0, 10.0, False)
    assert parse_price(None) == (None, None, None)
    assert format_price(0, 0, True) == "Free"
    assert format_price(20, 50, False) == "$20–$50"


def test_text_and_urls():
    assert html_to_text("<p>One&nbsp;line</p><p>Two<br/>Three</p>") == "One line\nTwo\nThree"
    assert summarize("A. " * 200).endswith(".")
    assert clean_url("https://x.com/a?utm_source=y&id=3#frag") == "https://x.com/a?id=3"
    assert clean_url("mailto:a@b.c") is None


def _event(**kw) -> Event:
    base = dict(source="terplink", source_url="https://example.com", title="x",
                start_time=datetime.fromisoformat("2026-10-10T20:00:00-04:00"))
    return Event(**{**base, **kw})


def test_rule_tags():
    assert rule_tags(_event(title="SEE Presents: Fall Spooky Movie Series")) == ["movie"]
    assert "hackathon" in rule_tags(_event(title="Bitcamp 2027 Interest Meeting"))
    assert "social" not in rule_tags(_event(title="Board meeting", description="Follow us on social media"))
    assert rule_tags(_event(title="zzz")) == ["other"]
    assert "food" in rule_tags(_event(title="GBM", extra={"free_food": True}))
    # Broad calendar topics only count when nothing specific matched.
    soccer = _event(source="umd_calendar", title="Maryland Women's Soccer vs Nebraska",
                    source_categories=["Arts, Entertainment and Culture", "Student Life"])
    assert rule_tags(soccer) == ["sports"]
    talk = _event(source="umd_calendar", title="Woe and Behold", source_categories=["Arts, Entertainment and Culture"])
    assert rule_tags(talk) == ["arts"]
    # An office's "CommunityService" theme (flu shots) is not volunteering; a student org's is.
    assert rule_tags(_event(title="Flu Shot Clinics", extra={"theme": "CommunityService"})) == ["other"]
    assert rule_tags(_event(title="Flu Shot Clinics", source_categories=["Service"])) == ["other"]
    assert "volunteering" in rule_tags(_event(title="Saturday shift", extra={"theme": "CommunityService",
                                                                             "student_organization": True}))
