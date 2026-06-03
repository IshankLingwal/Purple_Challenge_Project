from datetime import datetime, timezone, timedelta

from tests.utils import make_event


def test_funnel_counts_session_stages(client):
    base = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    events = [
        make_event(visitor_id="VIS_3001", event_type="ENTRY", timestamp=base, session_seq=1),
        make_event(
            visitor_id="VIS_3001",
            event_type="ZONE_ENTER",
            timestamp=base + timedelta(minutes=1),
            zone_id="MAKEUP",
            session_seq=2,
        ),
        make_event(
            visitor_id="VIS_3001",
            event_type="ZONE_DWELL",
            timestamp=base + timedelta(minutes=2),
            zone_id="MAKEUP",
            dwell_ms=30000,
            session_seq=3,
        ),
        make_event(
            visitor_id="VIS_3001",
            event_type="BILLING_QUEUE_JOIN",
            timestamp=base + timedelta(minutes=3),
            zone_id="BILLING",
            queue_depth=1,
            session_seq=4,
        ),
        make_event(
            visitor_id="VIS_3001",
            event_type="PURCHASE",
            timestamp=base + timedelta(minutes=4),
            zone_id="BILLING",
            session_seq=5,
        ),
        make_event(
            visitor_id="VIS_3001",
            event_type="EXIT",
            timestamp=base + timedelta(minutes=5),
            session_seq=6,
        ),
    ]

    response = client.post("/events/ingest", json={"events": events})
    assert response.status_code == 200

    funnel = client.get("/stores/STORE_BLR_002/funnel")
    assert funnel.status_code == 200
    body = funnel.json()

    assert body["entry"] == 1
    assert body["zone_visit"] == 1
    assert body["billing_queue"] == 1
    assert body["purchase"] == 1
    assert body["dropoff"]["entry_to_zone_visit"] == 0.0
    assert body["dropoff"]["zone_visit_to_billing_queue"] == 0.0
    assert body["dropoff"]["billing_queue_to_purchase"] == 0.0