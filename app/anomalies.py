import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from .storage import SessionLocal, events_table


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def get_anomalies(store_id: str):
    with SessionLocal() as session:
        rows = session.execute(
            select(events_table).where(events_table.c.store_id == store_id)
        ).all()

    if not rows:
        return {"store_id": store_id, "anomalies": []}

    events = []
    for row in rows:
        data = json.loads(row._mapping["metadata_json"])
        if data.get("is_staff", False):
            continue
        events.append(data)

    events.sort(key=lambda x: _parse_ts(x["timestamp"]))
    latest_ts = _parse_ts(events[-1]["timestamp"])

    anomalies = []

    billing_queue_count = sum(1 for e in events if e["event_type"] == "BILLING_QUEUE_JOIN")
    zone_activity = sum(1 for e in events if e["event_type"] in {"ZONE_ENTER", "ZONE_DWELL"})
    entry_count = sum(1 for e in events if e["event_type"] in {"ENTRY", "REENTRY"})
    purchase_count = sum(1 for e in events if e["event_type"] == "PURCHASE")

    if billing_queue_count >= 5:
        anomalies.append({
            "type": "BILLING_QUEUE_SPIKE",
            "severity": "WARN",
            "suggested_action": "Open another billing counter or add staff support.",
        })

    if zone_activity == 0 and entry_count > 0:
        anomalies.append({
            "type": "DEAD_ZONE",
            "severity": "INFO",
            "suggested_action": "Review zone visibility, signage, or camera placement.",
        })

    if datetime.now(timezone.utc) - latest_ts > timedelta(minutes=10):
        anomalies.append({
            "type": "STALE_FEED",
            "severity": "CRITICAL",
            "suggested_action": "Check camera feed, ingestion, or pipeline health.",
        })

    if entry_count >= 10 and purchase_count == 0:
        anomalies.append({
            "type": "CONVERSION_DROP",
            "severity": "WARN",
            "suggested_action": "Investigate billing friction, stock issues, or staffing.",
        })

    return {"store_id": store_id, "anomalies": anomalies}