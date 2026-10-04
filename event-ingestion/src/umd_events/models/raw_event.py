from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def compute_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class RawEvent(BaseModel):
    """One source record exactly as collected. Stored in RAW_EVENTS so events can be reparsed later."""

    ingestion_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source: str
    source_event_id: str
    source_url: str | None = None
    raw_data: dict[str, Any]
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scraper_version: str = "1"
    content_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            self.content_hash = compute_hash(self.raw_data)
