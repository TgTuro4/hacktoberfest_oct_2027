from datetime import datetime, timedelta

from umd_events.dedupe.deduplicator import deduplicate
from umd_events.models import Event
from umd_events.pipeline import prepare

T = datetime.fromisoformat("2026-10-09T20:00:00-04:00")


def ev(source, title, start=T, venue="Hoff Theater", **kw) -> Event:
    return prepare(Event(source=source, source_event_id=f"{source}-{title}-{start:%H%M}", title=title,
                         source_url=f"https://{source}.example/{abs(hash(title))}", start_time=start,
                         venue_name=venue, **kw))


def test_merges_same_event_across_sources():
    records = [
        ev("see", "SEE Presents: Spider-Man: Across the Spider-Verse", image_url="https://see/img.jpg"),
        ev("umd_calendar", "Spider-Man: Across the Spider Verse", T + timedelta(minutes=15), "Hoff Theatre, Stamp",
           description="A long description from the campus calendar."),
        ev("terplink", "Spider-Man Across the Spider-Verse", venue="Stamp Student Union - Hoff Theater"),
    ]
    result = deduplicate(records)
    assert len(result.events) == 1
    merged = result.events[0]
    assert merged.sources == ["see", "terplink", "umd_calendar"]
    assert merged.source == "see"  # most specific source wins
    assert merged.description == "A long description from the campus calendar."
    assert merged.image_url == "https://see/img.jpg"
    assert len(result.memberships) == 3


def test_does_not_merge_different_times_or_venues():
    records = [
        ev("see", "Movie Night: Coraline"),
        ev("terplink", "Movie Night: Coraline", T + timedelta(hours=2)),
        ev("umd_calendar", "Movie Night: Coraline", venue="Xfinity Center"),
    ]
    assert len(deduplicate(records).events) == 3


def test_within_one_source_only_exact_reposts_merge():
    # Generic title, no organizer: could be two clubs.
    records = [ev("terplink", "General Body Meeting"), ev("terplink", "General Body Meeting", venue="Stamp")]
    assert len(deduplicate(records).events) == 2
    # Same title/time/organizer posted twice (Hyattsville lists one movie under two IDs).
    records = [
        ev("hyattsville", "Free Movie Monday!", venue="City Building", organizer_name="City of Hyattsville"),
        ev("hyattsville", "Free Movie Monday!", venue="Hyattsville City Building", organizer_name="City of Hyattsville"),
    ]
    result = deduplicate(records)
    assert len(result.events) == 1 and len(result.memberships) == 2
    # Same club, same title, different time: separate events.
    records = [ev("terplink", "Tabling", organizer_name="Club A"), ev("terplink", "Tabling", T + timedelta(hours=2),
                                                                          organizer_name="Club A")]
    assert len(deduplicate(records).events) == 2


def test_exact_title_and_start_merge_despite_venue_text():
    records = [
        ev("terplink", "UMD Pride Felt Pennant Keychains", venue="The Mall"),
        ev("umd_calendar", "UMD Pride Felt Pennant Keychains", venue="Adele H. Stamp Student Union"),
    ]
    assert len(deduplicate(records).events) == 1


def test_external_ref_merges_even_with_different_titles():
    records = [
        ev("terps_after_dark", "Planting Healthy Roots: Bingo Night", external_refs={"terplink": "123"}),
        ev("terplink", "STAMP Plant Bingo", T + timedelta(minutes=5), external_refs={"terplink": "123"}),
    ]
    result = deduplicate(records)
    assert len(result.events) == 1
    assert set(result.events[0].tags) >= {"nightlife", "social"}


def test_sports_game_matches_calendar_listing():
    records = [
        ev("umd_athletics", "Maryland Field Hockey vs Delaware", venue="Field Hockey & Lacrosse Complex"),
        ev("umd_calendar", "Maryland Field Hockey vs Delaware", venue="Field Hockey and Lacrosse Complex"),
    ]
    assert len(deduplicate(records).events) == 1
