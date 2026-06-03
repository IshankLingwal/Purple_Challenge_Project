from datetime import datetime, timezone

from tests.utils import make_event


def test_ingest_is_idempotent(client):
    ts = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    event = make_event(
        visitor_id="VIS_1001",
        event_type="ENTRY",
        timestamp=ts,
        event_id="11111111-1111-1111-1111-111111111111",
    )

    r1 = client.post("/events/ingest", json={"events": [event]})
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["inserted"] == 1
    assert body1["skipped"] == 0
    assert body1["invalid"] == 0

    r2 = client.post("/events/ingest", json={"events": [event]})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["inserted"] == 0
    assert body2["skipped"] == 1