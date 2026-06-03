from datetime import datetime, timezone, timedelta

from tests.utils import make_event


def test_anomalies_detect_queue_spike_and_stale_feed(client):
    old_base = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)

    events = [
        make_event(
            visitor_id=f"VIS_Q{i}",
            event_type="BILLING_QUEUE_JOIN",
            timestamp=old_base + timedelta(minutes=i),
            zone_id="BILLING",
            queue_depth=i + 1,
            session_seq=1,
        )
        for i in range(5)
    ]

    response = client.post("/events/ingest", json={"events": events})
    assert response.status_code == 200

    anomalies = client.get("/stores/STORE_BLR_002/anomalies")
    assert anomalies.status_code == 200
    body = anomalies.json()

    anomaly_types = {item["type"] for item in body["anomalies"]}
    assert "BILLING_QUEUE_SPIKE" in anomaly_types
    assert "STALE_FEED" in anomaly_types