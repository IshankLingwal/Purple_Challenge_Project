import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select

from .storage import SessionLocal, events_table


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_events(store_id: str):
    with SessionLocal() as session:
        rows = session.execute(
            select(events_table).where(events_table.c.store_id == store_id)
        ).all()

    events = []
    for row in rows:
        data = json.loads(row._mapping["metadata_json"])
        if data.get("is_staff", False):
            continue
        events.append(data)

    events.sort(key=lambda x: _parse_ts(x["timestamp"]))
    return events


def _build_sessions(events):
    sessions_by_visitor = defaultdict(list)
    current_session_by_visitor = {}

    for event in events:
        visitor_id = event["visitor_id"]
        event_type = event["event_type"]

        if event_type in {"ENTRY", "REENTRY"}:
            if visitor_id in current_session_by_visitor:
                sessions_by_visitor[visitor_id].append(current_session_by_visitor[visitor_id])
            current_session_by_visitor[visitor_id] = [event]
            continue

        if visitor_id not in current_session_by_visitor:
            continue

        current_session_by_visitor[visitor_id].append(event)

        if event_type == "EXIT":
            sessions_by_visitor[visitor_id].append(current_session_by_visitor[visitor_id])
            del current_session_by_visitor[visitor_id]

    for visitor_id, session_events in current_session_by_visitor.items():
        sessions_by_visitor[visitor_id].append(session_events)

    return sessions_by_visitor


def get_funnel(store_id: str):
    events = _load_events(store_id)
    sessions_by_visitor = _build_sessions(events)

    entry = 0
    zone_visit = 0
    billing_queue = 0
    purchase = 0

    for visitor_sessions in sessions_by_visitor.values():
        for session_events in visitor_sessions:
            had_entry = any(e["event_type"] in {"ENTRY", "REENTRY"} for e in session_events)
            had_zone = any(e["event_type"] in {"ZONE_ENTER", "ZONE_DWELL"} for e in session_events)
            had_queue = any(e["event_type"] == "BILLING_QUEUE_JOIN" for e in session_events)
            had_purchase = any(e["event_type"] == "PURCHASE" for e in session_events)

            if had_entry:
                entry += 1
            if had_entry and had_zone:
                zone_visit += 1
            if had_entry and had_zone and had_queue:
                billing_queue += 1
            if had_entry and had_zone and had_queue and had_purchase:
                purchase += 1

    return {
        "store_id": store_id,
        "entry": entry,
        "zone_visit": zone_visit,
        "billing_queue": billing_queue,
        "purchase": purchase,
        "dropoff": {
            "entry_to_zone_visit": round(100 * (1 - zone_visit / entry), 2) if entry else 0,
            "zone_visit_to_billing_queue": round(100 * (1 - billing_queue / zone_visit), 2) if zone_visit else 0,
            "billing_queue_to_purchase": round(100 * (1 - purchase / billing_queue), 2) if billing_queue else 0,
        },
    }