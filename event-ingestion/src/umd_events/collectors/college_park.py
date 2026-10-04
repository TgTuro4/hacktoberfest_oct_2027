"""City of College Park calendar, via its CivicPlus iCalendar feeds."""

from __future__ import annotations

from .base import register
from .civicplus import CivicPlusCollector


@register
class CollegeParkCollector(CivicPlusCollector):
    source_name = "college_park"
    display_name = "City of College Park"
    scraper_version = "1"
    base_url = "https://www.collegeparkmd.gov"
    organizer = "City of College Park"
    # Only the event-like categories; council, board and public-works calendars are left out.
    categories = {
        14: "Main Calendar",
        24: "City Events",
        25: "Farmers Markets",
        29: "Seniors Program Events",
        31: "CPAE",  # College Park Arts Exchange
    }
