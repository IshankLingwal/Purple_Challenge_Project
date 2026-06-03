from datetime import datetime, timezone, timedelta

from tests.utils import make_event


def test_heatmap_returns_zone_summary(client):
    base = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    events = [
        make_event(
            visitor_id="VIS_H1",
            event_type="ZONE_ENTER",
            timestamp=base,
            zone_id="SKINCARE",
            session_seq=1,
        ),
        make_event(
            visitor_id="VIS_H1",
            event_type="ZONE_DWELL",
            timestamp=base + timedelta(minutes=1),
            zone_id="SKINCARE",
            dwell_ms=45000,
            session_seq=2,
        ),
        make_event(
            visitor_id="VIS_H2",
            event_type="ZONE_ENTER",
            timestamp=base + timedelta(minutes=2),
            zone_id="BILLING",
            session_seq=1,
        ),
        make_event(
            visitor_id="VIS_H2",
            event_type="ZONE_DWELL",
            timestamp=base + timedelta(minutes=3),
            zone_id="BILLING",
            dwell_ms=25000,
            session_seq=2,
        ),
    ]

    response = client.post("/events/ingest", json={"events": events})
    assert response.status_code == 200

    heatmap = client.get("/stores/STORE_BLR_002/heatmap")
    assert heatmap.status_code == 200
    body = heatmap.json()

    assert body["store_id"] == "STORE_BLR_002"
    zones = {item["zone_id"]: item for item in body["zones"]}

    assert "SKINCARE" in zones
    assert "BILLING" in zones
    assert zones["SKINCARE"]["visit_count"] >= 1
    assert zones["BILLING"]["visit_count"] >= 1