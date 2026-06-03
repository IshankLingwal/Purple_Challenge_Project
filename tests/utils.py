from datetime import datetime, timezone
from uuid import uuid4


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_event(
    *,
    store_id: str = "STORE_BLR_002",
    camera_id: str = "CAM_ENTRY_01",
    visitor_id: str = "VIS_0001",
    event_type: str = "ENTRY",
    timestamp: datetime | None = None,
    zone_id: str | None = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 0.95,
    queue_depth: int | None = None,
    sku_zone: str | None = None,
    session_seq: int = 1,
    event_id: str | None = None,
):
    timestamp = timestamp or datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    return {
        "event_id": event_id or str(uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": iso(timestamp),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone": sku_zone,
            "session_seq": session_seq,
        },
    }