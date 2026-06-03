from datetime import datetime, timezone, timedelta

from tests.utils import make_event


def test_metrics_after_basic_journey(client):
    base = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    events = [
        make_event(visitor_id="VIS_2001", event_type="ENTRY", timestamp=base, session_seq=1),
        make_event(
            visitor_id="VIS_2001",
            event_type="ZONE_ENTER",
            timestamp=base + timedelta(minutes=1),
            zone_id="SKINCARE",
            session_seq=2,
        ),
        make_event(
            visitor_id="VIS_2001",
            event_type="ZONE_DWELL",
            timestamp=base + timedelta(minutes=2),
            zone_id="SKINCARE",
            dwell_ms=30000,
            session_seq=3,
        ),
        make_event(
            visitor_id="VIS_2001",
            event_type="BILLING_QUEUE_JOIN",
            timestamp=base + timedelta(minutes=3),
            zone_id="BILLING",
            queue_depth=2,
            session_seq=4,
        ),
        make_event(
            visitor_id="VIS_2001",
            event_type="PURCHASE",
            timestamp=base + timedelta(minutes=4),
            zone_id="BILLING",
            session_seq=5,
        ),
        make_event(
            visitor_id="VIS_2001",
            event_type="EXIT",
            timestamp=base + timedelta(minutes=5),
            session_seq=6,
        ),
    ]

    response = client.post("/events/ingest", json={"events": events})
    assert response.status_code == 200

    metrics = client.get("/stores/STORE_BLR_002/metrics")
    assert metrics.status_code == 200
    body = metrics.json()

    assert body["unique_visitors"] == 1
    assert body["entry_count"] == 1
    assert body["exit_count"] == 1
    assert body["purchase_count"] == 1
    assert body["billing_queue_count"] == 1
    assert body["conversion_rate"] == 1.0
    assert body["abandonment_rate"] == 0.0
    assert "SKINCARE" in body["avg_dwell_by_zone"]