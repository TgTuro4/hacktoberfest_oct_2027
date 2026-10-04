"""Venue normalization and the local venue lookup table.

Venues resolve to the building/place level ("Hoff Theater" -> Stamp Student Union) so the deduplicator and
geolocation can compare places even when sources name different rooms in the same building. The raw room
name is kept in ``Event.venue_name``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from .titles import strip_accents

UMD_ADDRESS = "College Park, MD 20742"


@dataclass(frozen=True)
class Venue:
    venue_id: str
    canonical_name: str
    latitude: float
    longitude: float
    address: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    is_umd: bool = True


def _v(venue_id, name, lat, lon, aliases, address=UMD_ADDRESS, is_umd=True) -> Venue:
    return Venue(venue_id, name, lat, lon, address, tuple(aliases), is_umd)


# Curated venues: the places events actually happen. Checked before the generic campus-building list.
# Coordinates come from the umd.io building list and OpenStreetMap.
KNOWN_VENUES: list[Venue] = [
    _v("stamp-student-union", "Adele H. Stamp Student Union", 38.98816, -76.94472,
       ["stamp student union", "adele h stamp", "the stamp", "stamp", "hoff theater", "hoff theatre",
        "grand ballroom", "colony ballroom", "baltimore room", "prince georges room", "atrium stamp",
        "benjamin banneker", "juan ramon jimenez room", "terpzone", "terp zone", "ssu"],
       "3972 Campus Dr, College Park, MD 20742"),
    _v("clarice-smith-center", "The Clarice Smith Performing Arts Center", 38.99068, -76.95044,
       ["clarice smith performing arts center", "the clarice", "clarice", "dekelboum concert hall",
        "ina and jack kay theatre", "kay theater", "kay theatre", "gildenhorn recital hall",
        "dance theater", "dance theatre", "kogod theater", "kogod theatre", "smith lecture hall",
        "performing arts library", "8270 alumni"],
       "8270 Alumni Dr, College Park, MD 20742"),
    _v("xfinity-center", "Xfinity Center", 38.99563, -76.941337,
       ["xfinity center", "xfinity", "comcast center"], "8500 Paint Branch Dr, College Park, MD 20742"),
    _v("secu-stadium", "SECU Stadium", 38.99034, -76.94752,
       ["secu stadium", "maryland stadium", "byrd stadium", "capital one field"],
       "90 Stadium Dr, College Park, MD 20742"),
    _v("ludwig-field", "Ludwig Field", 38.98788, -76.95057, ["ludwig field", "kehoe track"]),
    _v("field-hockey-lacrosse-complex", "Field Hockey & Lacrosse Complex", 38.994727, -76.936861,
       ["field hockey and lacrosse complex", "field hockey lacrosse complex"]),
    _v("bob-smith-stadium", "Bob \"Turtle\" Smith Stadium", 38.988942, -76.944113,
       ["bob turtle smith stadium", "turtle smith stadium", "shipley field"]),
    _v("taylor-softball-stadium", "Robert E. Taylor Softball Stadium", 38.99629, -76.93975,
       ["taylor softball stadium", "robert e taylor softball stadium", "softball stadium"]),
    _v("eppley-recreation-center", "Eppley Recreation Center", 38.99358, -76.94527,
       ["eppley recreation center", "eppley campus recreation center", "eppley", "erc"]),
    _v("ritchie-coliseum", "Ritchie Coliseum", 38.985048, -76.936456, ["ritchie coliseum"]),
    _v("mckeldin-mall", "McKeldin Mall", 38.98599, -76.94227, ["mckeldin mall"]),
    _v("mckeldin-library", "McKeldin Library", 38.98598, -76.9451, ["mckeldin library", "mckeldin"]),
    _v("memorial-chapel", "Memorial Chapel", 38.98415, -76.940866, ["memorial chapel"]),
    _v("iribe-center", "Brendan Iribe Center", 38.98916, -76.93644, ["brendan iribe center", "iribe center", "iribe"]),
    _v("umd-golf-course", "University of Maryland Golf Course", 38.991133, -76.954707,
       ["university of maryland golf course", "umd golf course"]),
    # Off campus, near College Park.
    _v("college-park-city-hall", "College Park City Hall", 38.981032, -76.93806,
       ["city hall plaza", "college park city hall", "7401 baltimore"],
       "7401 Baltimore Ave, College Park, MD 20740", False),
    _v("duvall-field", "Duvall Field", 38.999949, -76.925294, ["duvall field", "9100 rhode island"],
       "9100 Rhode Island Ave, College Park, MD 20740", False),
    _v("old-parish-house", "Old Parish House", 38.979099, -76.931114, ["old parish house", "4711 knox"],
       "4711 Knox Rd, College Park, MD 20740", False),
    _v("davis-hall-college-park", "Davis Hall", 39.003941, -76.920865, ["davis hall", "9217 51st"],
       "9217 51st Ave, College Park, MD 20740", False),
    _v("college-park-community-center", "College Park Community Center", 38.987245, -76.927327,
       ["college park community center", "5051 pierce"], "5051 Pierce Ave, College Park, MD 20740", False),
    _v("hyattsville-city-building", "Hyattsville City Building", 38.952928, -76.94178,
       ["hyattsville city building", "hyattsville city hall", "4310 gallatin"],
       "4310 Gallatin St, Hyattsville, MD 20781", False),
    _v("college-park-aviation-museum", "College Park Aviation Museum", 38.978837, -76.922255,
       ["college park aviation museum", "aviation museum", "1985 corporal frank scott"],
       "1985 Corporal Frank Scott Dr, College Park, MD 20740", False),
    _v("riversdale-house-museum", "Riversdale House Museum", 38.960237, -76.931838,
       ["riversdale house museum", "riversdale"], "4811 Riverdale Rd, Riverdale Park, MD 20737", False),
    _v("bladensburg-waterfront-park", "Bladensburg Waterfront Park", 38.93523, -76.93869,
       ["bladensburg waterfront park", "bladensburg waterfront"], "4601 Annapolis Rd, Bladensburg, MD 20710", False),
    _v("brentwood-arts-exchange", "Brentwood Arts Exchange", 38.939309, -76.954501,
       ["brentwood arts exchange"], "3901 Rhode Island Ave, Brentwood, MD 20722", False),
    _v("langley-park-community-center", "Langley Park Community Center", 38.992984, -76.981646,
       ["langley park community center", "live well langley"], "1500 Merrimac Dr, Hyattsville, MD 20783", False),
]

# Common short names for campus buildings -> building code in the umd.io list.
BUILDING_ALIASES = {
    "armory": "ARM",
    "reckord armory": "ARM",
    "kirwan hall": "MTH",
    "math building": "MTH",
    "math": "MTH",
    "art sociology": "ASY",
    "art socy": "ASY",
    "artsoc": "ASY",
    "esj": "ESJ",
    "kim engineering": "KEB",
    "csic": "CSI",
    "hj patterson": "HJP",
    "marie mount": "MMH",
}

ONLINE_PATTERN = re.compile(r"\b(zoom|online|virtual|webinar|microsoft teams|google meet|livestream)\b", re.I)


def normalize_venue_name(value: str | None) -> str:
    if not value:
        return ""
    value = strip_accents(value).lower()
    value = value.replace("theatre", "theater").replace("&", " and ").replace("'", "")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\b(the|university of maryland|umd|md|maryland|usa|\d{5}(?: \d{4})?)\b", " ", value)
    return " ".join(value.split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(value).lower()).strip("-")


def _phrase_in(phrase: str, text: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


class VenueIndex:
    def __init__(self, curated: list[Venue], buildings: list[dict]):
        self.curated = curated
        self._curated_aliases = sorted(
            ((normalize_venue_name(alias) or alias, venue) for venue in curated for alias in venue.aliases),
            key=lambda pair: -len(pair[0]),
        )
        self.by_code: dict[str, Venue] = {}
        self._building_names: list[tuple[str, Venue]] = []
        for b in buildings:
            name = re.sub(r"\s*\((?:residence hall|baseball)\)\s*", "", b["name"], flags=re.I).strip()
            venue = Venue(f"umd-{_slug(name)}", name, b["lat"], b["lon"], UMD_ADDRESS,
                          tuple(filter(None, [b.get("code")])), True)
            if b.get("code"):
                self.by_code[b["code"].upper()] = venue
            normalized = normalize_venue_name(name)
            if len(normalized) >= 6:
                self._building_names.append((normalized, venue))
        self._building_names.sort(key=lambda pair: -len(pair[0]))
        # "Jimenez 2120", "Symons 0200": first word of a building name, when it identifies one building.
        first_words: dict[str, list[Venue]] = {}
        for normalized, venue in self._building_names:
            first_words.setdefault(normalized.split()[0], []).append(venue)
        self.by_first_word = {w: vs[0] for w, vs in first_words.items() if len(vs) == 1 and len(w) >= 5}
        self._aliases = sorted(
            ((alias, self.by_code[code]) for alias, code in BUILDING_ALIASES.items() if code in self.by_code),
            key=lambda pair: -len(pair[0]),
        )
        self.by_id = {v.venue_id: v for v in curated} | {v.venue_id: v for _, v in self._building_names} | {
            v.venue_id: v for v in self.by_code.values()
        }

    def resolve(self, name: str | None, address: str | None = None) -> Venue | None:
        text = normalize_venue_name(" ".join(filter(None, [name, address])))
        if not text:
            return None
        for alias, venue in self._curated_aliases:
            if _phrase_in(alias, text):
                return venue
        if name:
            # "ASY Art-Socy 3207" (leading code) or "William E. Kirwan Hall (MTH 0104)" (code in parentheses)
            for pattern in (r"^\s*([A-Z]{2,4})\b", r"\(([A-Z]{2,4})[\s-]?[A-Z]?\d"):
                code = re.search(pattern, name)
                if code and code.group(1) in self.by_code:
                    return self.by_code[code.group(1)]
        for alias, venue in self._aliases:
            if _phrase_in(alias, text):
                return venue
        for building, venue in self._building_names:
            if _phrase_in(building, text):
                return venue
        room = re.match(r"\s*([a-z][a-z.'-]+)\s+(?:room\s+)?[a-z]?\d{3,4}\b", text)
        if room and room.group(1) in self.by_first_word:
            return self.by_first_word[room.group(1)]
        return None


@lru_cache(maxsize=1)
def venue_index() -> VenueIndex:
    buildings = json.loads(resources.files("umd_events.data").joinpath("umd_buildings.json").read_text("utf-8"))
    return VenueIndex(KNOWN_VENUES, buildings)
