"""Optional text embeddings for semantic recommendations.

Uses fastembed (ONNX, CPU-only, no PyTorch) with BAAI/bge-small-en-v1.5, a free open-source 384-dimension
model. Install with ``uv sync --extra embeddings``. The first run downloads the model (about 130 MB).
Snowflake column type: VECTOR(FLOAT, 384).
"""

from __future__ import annotations

import logging

from ..models import Event

log = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384


def embedding_text(event: Event) -> str:
    parts = [event.title, event.summary or "", ", ".join(event.tags), event.venue_name or "", event.organizer_name or ""]
    return " | ".join(p for p in parts if p)[:2000]


def embed_events(events: list[Event]) -> dict[str, list[float]]:
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:  # optional dependency
        raise RuntimeError("fastembed is not installed: run `uv sync --extra embeddings`") from exc
    model = TextEmbedding(MODEL_NAME)
    vectors = model.embed([embedding_text(e) for e in events], batch_size=64)
    return {e.event_id: [round(float(x), 6) for x in v] for e, v in zip(events, vectors)}
