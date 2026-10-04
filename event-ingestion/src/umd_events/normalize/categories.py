"""Event taxonomy and the mapping from each source's own category labels onto it."""

from __future__ import annotations

TAXONOMY: tuple[str, ...] = (
    "sports",
    "movie",
    "concert",
    "music",
    "comedy",
    "theater",
    "dance",
    "arts",
    "gaming",
    "hackathon",
    "technology",
    "career",
    "academic",
    "research",
    "workshop",
    "social",
    "cultural",
    "food",
    "outdoors",
    "fitness",
    "intramural",
    "volunteering",
    "community",
    "nightlife",
    "student_organization",
    "lecture",
    "festival",
    "other",
)

_TAXONOMY_SET = set(TAXONOMY)

# Lower-cased source label -> taxonomy tags. Labels not listed here are ignored.
SOURCE_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    # TerpLink themes and categories
    "arts": ("arts",),
    "art": ("arts",),
    "athletics": ("sports",),
    "communityservice": ("volunteering",),
    "community service": ("volunteering",),
    "service": ("volunteering",),
    "cultural": ("cultural",),
    "social": ("social",),
    "thoughtfullearning": ("academic",),
    "learning": ("academic",),
    "entertainment": ("social",),
    "music": ("music",),
    "performance": ("arts",),
    "career": ("career",),
    "career development": ("career",),
    "professional development": ("career",),
    "technology": ("technology",),
    "sports": ("sports",),
    "recreation": ("fitness",),
    "health & wellness": (),
    "food": ("food",),
    "free food": ("food",),
    "terps after dark": ("nightlife", "social"),
    "gaming": ("gaming",),
    "volunteer": ("volunteering",),
    "workshop": ("workshop",),
    "fundraising": ("community",),
    # UMD calendar event topics and tags
    "arts, entertainment and culture": ("arts",),
    "arts and culture": ("arts",),
    "athletics and recreation": ("sports",),
    "community engagement": ("community",),
    "diversity and inclusion": ("cultural",),
    "research": ("research",),
    "academics": ("academic",),
    "student life": ("social",),
    "lectures and seminars": ("lecture",),
    "lecture": ("lecture",),
    "workshops and training": ("workshop",),
    "career and professional development": ("career",),
    "film": ("movie",),
    "film screening": ("movie",),
    "theatre": ("theater",),
    "theater": ("theater",),
    "dance": ("dance",),
    "concert": ("concert", "music"),
    "festival": ("festival",),
    "conference": ("academic",),
    # PG Parks / city calendars
    "nature & outdoor": ("outdoors",),
    "nature and outdoor": ("outdoors",),
    "nature &amp; outdoor": ("outdoors",),
    "history": ("cultural",),
    "black history": ("cultural",),
    "holidays & celebrations": ("festival",),
    "holidays &amp; celebrations": ("festival",),
    "city events": ("community",),
    "community events": ("community",),
    "cpae": ("arts",),
    "seniors program events": ("community",),
    # Ticketmaster segments / genres
    "comedy": ("comedy",),
    "theatre (ticketmaster)": ("theater",),
    "football": ("sports",),
    "basketball": ("sports",),
    "hockey": ("sports",),
    "baseball": ("sports",),
    "soccer": ("sports",),
    "rock": ("concert", "music"),
    "pop": ("concert", "music"),
    "hip-hop/rap": ("concert", "music"),
    "r&b": ("concert", "music"),
    "jazz": ("concert", "music"),
    "classical": ("concert", "music"),
    "country": ("concert", "music"),
    "alternative": ("concert", "music"),
    "family": ("community",),
}


def map_source_categories(labels: list[str]) -> set[str]:
    tags: set[str] = set()
    for label in labels:
        tags.update(SOURCE_CATEGORY_MAP.get(label.strip().lower(), ()))
    return tags


def valid_tags(tags) -> list[str]:
    """Keep only taxonomy tags, de-duplicated, in taxonomy order."""
    wanted = {t.strip().lower() for t in tags if isinstance(t, str)}
    return [t for t in TAXONOMY if t in wanted and t in _TAXONOMY_SET]
