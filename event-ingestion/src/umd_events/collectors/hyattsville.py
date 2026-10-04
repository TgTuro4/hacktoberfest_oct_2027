"""City of Hyattsville calendar, via its CivicPlus iCalendar feeds."""

from __future__ import annotations

from .base import register
from .civicplus import CivicPlusCollector


@register
class HyattsvilleCollector(CivicPlusCollector):
    source_name = "hyattsville"
    display_name = "City of Hyattsville"
    scraper_version = "1"
    tier = 2
    base_url = "https://www.hyattsville.org"
    organizer = "City of Hyattsville"
    categories = {14: "Main City Calendar", 35: "Community Events"}
