"""Source registration. Adding a source = one collector module + one import line here."""

from .base import REGISTRY, BaseCollector, CollectorResult

# Tier 1 (MVP)
from . import umd_calendar  # noqa: F401,E402
from . import terplink  # noqa: F401,E402
from . import see  # noqa: F401,E402
from . import terps_after_dark  # noqa: F401,E402
from . import athletics  # noqa: F401,E402
from . import clarice  # noqa: F401,E402
from . import college_park  # noqa: F401,E402

# Tier 2 (stretch)
from . import ticketmaster  # noqa: F401,E402
from . import recwell  # noqa: F401,E402
from . import pg_parks  # noqa: F401,E402
from . import hyattsville  # noqa: F401,E402

__all__ = ["REGISTRY", "BaseCollector", "CollectorResult"]
