"""Event tagging.

1. ``rule_tags``: deterministic, instant. Source category labels plus keyword patterns. Always runs.
2. ``OllamaTagger``: optional local open-source LLM (via Ollama). Runs after deterministic parsing, only on
   events whose content changed (cached by content hash), and only when enabled.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import timedelta
from typing import Callable

import requests

from ..models import Event
from ..normalize.categories import TAXONOMY, map_source_categories, valid_tags

log = logging.getLogger(__name__)


def _rx(*patterns: str) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b", re.IGNORECASE)


# tag -> pattern matched against title + summary + description
KEYWORD_RULES: dict[str, re.Pattern] = {
    "movie": _rx(r"movies?", "film(?:s| screening| series| festival)?", "screenings?", "cinema", "flicks?",
                 "dive-in movie", "movie night"),
    "concert": _rx("concerts?", "live music", "recital", "orchestra", "symphony", "philharmonic", "choir",
                   "chorale", "ensemble", "band performance", "jazz (?:jam|combo|band)s?", "open mic"),
    "music": _rx("music(?:al)?", "concerts?", "dj", "jazz", "orchestra", "choir", "piano", "songwriter",
                 "a cappella", "hip hop", "k-?pop", "karaoke"),
    "comedy": _rx("comedy", "comedian", "stand-?up", "improv", "sketch show", "laugh"),
    "theater": _rx("theat(?:er|re)", "musical", "opera", "a play", "stage production", "drama(?:tic)? production",
                   "playwright", "shakespeare"),
    "dance": _rx("dance(?:s|rs)?", "dancing", "ballet", "salsa", "bachata", "tap danc\\w*", "hip hop dance",
                 "bhangra", "k-?pop dance", "swing"),
    "arts": _rx("art(?:s)?", "exhibit(?:ion)?", "gallery", "painting", "paint night", "crafts?", "pottery",
                "ceramics", "drawing", "sculpture", "photography", "museum", "knitting", "needle arts", "woodshop"),
    "gaming": _rx("game night", "video games?", "board games?", "gaming", "e-?sports", "smash bros", "valorant",
                  "league of legends", "mario kart", "chess", "d&d", "dungeons", "tabletop"),
    "hackathon": _rx("hackathons?", "hack night", "bitcamp", "technica", "hackumbc", "hack ?day"),
    "technology": _rx("coding", "software", "programming", "python", "artificial intelligence", "ai",
                      "machine learning", "data science", "cybersecurity", "robotics", "computer science",
                      "web development", "app development", "3d printing", "quantum", "github"),
    "career": _rx("career(?:s)?", "resume", "résumé", "internships?", "job fair", "networking", "recruit(?:ing|ment)?",
                  "employer", "info(?:rmation)? session", "linkedin", "interview(?:ing)? (?:prep|skills)",
                  "professional development", "grad school"),
    "academic": _rx("academic", "study (?:session|group|break)", "tutoring", "office hours", "thesis",
                    "dissertation defense", "advising", "commencement", "convocation"),
    "research": _rx("research", "symposium", "colloquium", "dissertation", "poster session", "lab tour"),
    "lecture": _rx("lectures?", "talk", "keynote", "speaker series", "seminar", "colloquium", "panel(?: discussion)?",
                   "fireside chat", "book talk", "q&a", "conversation with"),
    "workshop": _rx("workshops?", "training", "clinic", "bootcamp", "how to", "learn to", "masterclass",
                    "master class", "info session"),
    "social": _rx("social", "mixer", "party", "hangout", "meet(?:-| and )greet", "mingle", "bingo", "trivia",
                  "game night", "karaoke", "welcome back", "ice cream", "picnic", "potluck", "speed friending"),
    "cultural": _rx("cultural?", "heritage month", "diwali", "holi", "lunar new year", "eid", "ramadan",
                    "hispanic heritage", "latin[aoex]?", "black history", "pride", "asian american",
                    "filipino", "african", "caribbean", "native american", "indigenous", "international"),
    "food": _rx("free food", "food", "pizza", "dinner", "lunch", "breakfast", "brunch", "snacks?", "tasting",
                "bbq", "barbecue", "cook(?:ing|-off)?", "bake sale", "farmers market", "food truck", "dessert",
                "refreshments"),
    "outdoors": _rx("hik(?:e|ing)", "outdoors?", "kayak(?:ing)?", "canoe(?:ing)?", "camping", "backpacking",
                    "garden(?:ing)?", "nature", "trail", "bird(?:ing| walk)", "climbing", "invasive plants",
                    "tree planting", "park clean-?up"),
    "fitness": _rx("yoga", "zumba", "fitness", "workout", "pilates", "5k", "fun run", "run club", "tai chi",
                   "spin class", "hiit", "bootcamp", "meditation", "wellness walk", "exercise"),
    "sports": _rx("football", "basketball", "soccer", "volleyball", "lacrosse", "baseball", "softball", "wrestling",
                  "gymnastics", "field hockey", "tennis", "track and field", "cross country", "golf", "swim meet",
                  "terps vs", "maryland vs", "tailgate", "pickleball", "badminton", "flag football", "futsal"),
    "intramural": _rx("intramurals?", "imleagues"),
    "volunteering": _rx("volunteer(?:s|ing)?", "community service", "service project", "clean-?up", "donation drive",
                        "food drive", "blood drive", "habitat for humanity", "mentoring"),
    "community": _rx("community", "neighborhood", "city of college park", "town hall", "family day",
                     "farmers market", "residents"),
    "nightlife": _rx("terps after dark", "late night", "late-night", "midnight", "night owls?", "after dark",
                     "glow party", "rave"),
    "festival": _rx("festival", "fest", "fair", "carnival", "block party", "celebration", "homecoming",
                    "winter wonderland", "art walk"),
}

# Specific enough to trust when they appear anywhere in the description.
BODY_MATCH_TAGS = {
    "movie", "concert", "comedy", "theater", "dance", "hackathon", "gaming", "career", "outdoors", "fitness",
    "volunteering", "intramural", "nightlife", "research",
}

# Source-level defaults.
SOURCE_TAGS: dict[str, tuple[str, ...]] = {
    "umd_athletics": ("sports",),
    "terps_after_dark": ("nightlife", "social"),
    "recwell": ("intramural", "sports"),
    "clarice": ("arts",),
    "college_park": ("community",),
    "hyattsville": ("community",),
    "pg_parks": ("community",),
}

_MEETING = _rx(r"gbm", "general body(?: meeting)?", "general meeting", "body meeting", "(?:weekly|club|chapter) meeting",
               "e-?board", "practices?", "rehearsals?", "office hours", "info(?:rmation)? session", "interest meeting")
_CLASS = _rx("class(?:es)?", "lessons?", "course", "clinic", "tai chi", "zumba", "yoga")
_EXHIBIT = _rx("exhibit(?:ion)?", "on display", "installation", "gallery")
_SCREENING = _rx("screenings?", "movie", "film", "flicks")


# Sources whose category labels are picked per event and are specific enough to trust. Other sources label
# broadly (the UMD calendar files a soccer game under "Arts, Entertainment and Culture"; every College Park
# Arts Exchange booking, yoga included, is "CPAE"), so their labels only count when nothing else matched.
SPECIFIC_CATEGORY_SOURCES = {"terplink", "see", "terps_after_dark", "pg_parks", "ticketmaster"}

# Offices label services they offer (flu shots) as "Service"/"CommunityService"; that only means
# volunteering when a student organization posts it.
_SERVICE_LABELS = {"service", "community service", "communityservice"}

# TerpLink's single "theme" per event.
THEME_TAGS = {
    "Arts": ("arts",),
    "Athletics": ("sports",),
    "CommunityService": ("volunteering",),
    "Cultural": ("cultural",),
    "Social": ("social",),
    "ThoughtfulLearning": ("academic",),
    "Fundraising": ("community",),
}


def rule_tags(event: Event) -> list[str]:
    defaults = set(SOURCE_TAGS.get(event.source, ()))
    specific = set(event.tags)  # set by the collector
    if event.source in SPECIFIC_CATEGORY_SOURCES:
        labels = event.source_categories
        if not event.extra.get("student_organization"):
            labels = [c for c in labels if c.strip().lower() not in _SERVICE_LABELS]
        specific |= map_source_categories(labels)
    title = event.title or ""
    headline = " ".join(filter(None, [title, event.summary]))
    body = " ".join(filter(None, [headline, (event.description or "")[:1500]]))
    for tag, pattern in KEYWORD_RULES.items():
        # Broad tags ("social", "food", "cultural") must match the title or summary; a passing mention deep in
        # a description ("follow us on social media") is not enough.
        if pattern.search(body if tag in BODY_MATCH_TAGS else headline):
            specific.add(tag)
    if event.extra.get("free_food"):
        specific.add("food")
    if "concert" in specific:
        specific.add("music")

    tags = specific | defaults
    if not specific - defaults:
        # Nothing specific: fall back to the source's broad labels and TerpLink's theme.
        if event.source not in SPECIFIC_CATEGORY_SOURCES:
            tags |= map_source_categories(event.source_categories)
        theme = THEME_TAGS.get(event.extra.get("theme") or "", ())
        if theme == ("volunteering",) and not event.extra.get("student_organization"):
            theme = ()
        tags |= set(theme)

    if event.source in ("terplink", "see", "terps_after_dark") and event.extra.get("student_organization"):
        tags.add("student_organization")
    if event.source == "umd_athletics" or event.event_type == "sports_game":
        tags -= {"gaming", "arts", "music", "dance", "theater", "academic"}
        tags.add("sports")
    if not tags:
        tags.add("other")
    elif len(tags) > 1:
        tags.discard("other")
    return valid_tags(tags)


def infer_event_type(event: Event) -> str:
    if event.event_type:
        return event.event_type
    title = event.title or ""
    if event.end_time and event.end_time - event.start_time > timedelta(days=3):
        return "exhibit" if _EXHIBIT.search(title + " " + (event.summary or "")) else "ongoing"
    if _MEETING.search(title):
        return "meeting"
    if _SCREENING.search(title):
        return "screening"
    if _EXHIBIT.search(title):
        return "exhibit"
    if _CLASS.search(title):
        return "class"
    return "activity"


PROMPT = """Given this university/local event, return zero or more tags from this allowed taxonomy.
Only use tags from the list. Return JSON only, like {{"tags": ["movie", "social"]}}.

Title:
{title}

Description:
{description}

Venue:
{venue}

Organizer:
{organizer}

Allowed tags:
{taxonomy}"""


class OllamaTagger:
    """Tags events with a local open-source model through Ollama's HTTP API (https://ollama.com)."""

    def __init__(self, host: str, model: str, timeout_s: float = 120):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def available(self) -> tuple[bool, str]:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=3)
            response.raise_for_status()
        except requests.RequestException:
            return False, f"Ollama is not running at {self.host}"
        names = {m.get("name", "") for m in response.json().get("models", [])}
        if self.model not in names and f"{self.model}:latest" not in names:
            return False, f"model {self.model!r} not pulled (run: ollama pull {self.model})"
        return True, "ok"

    def tag(self, event: Event) -> list[str]:
        prompt = PROMPT.format(
            title=event.title,
            description=(event.description or event.summary or "")[:1200],
            venue=event.venue_name or "",
            organizer=event.organizer_name or "",
            taxonomy=json.dumps([t for t in TAXONOMY if t != "other"]),
        )
        response = requests.post(
            f"{self.host}/api/generate",
            json={"model": self.model, "prompt": prompt, "format": "json", "stream": False,
                  "options": {"temperature": 0, "num_predict": 80}},
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        try:
            payload = json.loads(response.json().get("response") or "{}")
        except json.JSONDecodeError:
            return []
        return valid_tags(payload.get("tags") or [])

    def tag_many(self, events: list[Event], cache_get: Callable[[str], list[str] | None],
                 cache_put: Callable[[str, list[str]], None], limit: int) -> int:
        """Tag events (fewest rule tags first), using and filling the cache. Returns how many hit the model."""
        todo = [e for e in events if cache_get(e.content_hash) is None]
        todo.sort(key=lambda e: len(e.tags))
        done = 0
        started = time.monotonic()
        for event in todo[:limit]:
            try:
                tags = self.tag(event)
            except requests.RequestException as exc:
                log.warning("LLM tagging stopped: %s", exc)
                break
            cache_put(event.content_hash, tags)
            done += 1
        if done:
            log.info("LLM tagged %d events with %s in %.0fs (%d still pending)", done, self.model,
                     time.monotonic() - started, max(0, len(todo) - done))
        return done
