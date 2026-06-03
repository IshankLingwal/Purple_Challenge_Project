import json
from collections import defaultdict

from sqlalchemy import select

from .storage import SessionLocal, events_table


def get_heatmap(store_id: str):
    with SessionLocal() as session:
        rows = session.execute(
            select(events_table).where(events_table.c.store_id == store_id)
        ).all()

    zone_visits = defaultdict(int)
    zone_dwell = defaultdict(int)

    for row in rows:
        data = json.loads(row._mapping["metadata_json"])

        if data.get("is_staff", False):
            continue

        zone = data.get("zone_id")
        if not zone:
            continue

        event_type = data.get("event_type")

        if event_type in {"ZONE_ENTER", "ZONE_DWELL"}:
            zone_visits[zone] += 1

        if event_type == "ZONE_DWELL":
            zone_dwell[zone] += data.get("dwell_ms", 0)

    heatmap = []

    all_zones = set(zone_visits.keys()) | set(zone_dwell.keys())

    for zone in all_zones:
        visits = zone_visits[zone]
        avg_dwell = round(zone_dwell[zone] / visits, 2) if visits else 0

        heatmap.append(
            {
                "zone_id": zone,
                "visit_count": visits,
                "avg_dwell_ms": avg_dwell,
            }
        )

    heatmap.sort(key=lambda x: x["visit_count"], reverse=True)

    return {
        "store_id": store_id,
        "zones": heatmap,
    }