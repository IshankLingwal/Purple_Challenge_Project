import json
from typing import Any

from fastapi import FastAPI, HTTPException
from sqlalchemy import select, insert
from sqlalchemy.exc import SQLAlchemyError

from .models import IngestBatch
from .storage import init_db, SessionLocal, events_table
from .metrics import compute_basic_metrics
from .funnel import get_funnel
from .anomalies import get_anomalies
from .heatmap import get_heatmap

app = FastAPI(title="Store Intelligence API")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events/ingest")
def ingest(batch: IngestBatch):
    inserted = 0
    skipped = 0
    invalid = 0
    errors: list[dict[str, Any]] = []

    try:
        with SessionLocal() as session:
            for idx, event in enumerate(batch.events):
                try:
                    exists = session.execute(
                        select(events_table.c.event_id).where(
                            events_table.c.event_id == str(event.event_id)
                        )
                    ).first()

                    if exists:
                        skipped += 1
                        continue

                    session.execute(
                        insert(events_table).values(
                            event_id=str(event.event_id),
                            store_id=event.store_id,
                            camera_id=event.camera_id,
                            visitor_id=event.visitor_id,
                            event_type=event.event_type,
                            timestamp=event.timestamp.isoformat(),
                            zone_id=event.zone_id,
                            dwell_ms=event.dwell_ms,
                            is_staff=event.is_staff,
                            confidence=event.confidence,
                            metadata_json=event.model_dump_json(),
                        )
                    )

                    inserted += 1

                except Exception as e:
                    invalid += 1
                    errors.append(
                        {
                            "index": idx,
                            "error": str(e),
                        }
                    )

            session.commit()

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail={"error": "database unavailable"},
        )

    return {
        "inserted": inserted,
        "skipped": skipped,
        "invalid": invalid,
        "errors": errors,
    }


@app.get("/stores/{store_id}/metrics")
def store_metrics(store_id: str):
    with SessionLocal() as session:
        rows = session.execute(
            select(events_table).where(
                events_table.c.store_id == store_id
            )
        ).all()

    events = []

    for row in rows:
        payload = row._mapping["metadata_json"]
        data = json.loads(payload)

        events.append(
            {
                "visitor_id": data["visitor_id"],
                "event_type": data["event_type"],
                "zone_id": data.get("zone_id"),
                "dwell_ms": data.get("dwell_ms", 0),
                "is_staff": data.get("is_staff", False),
                "timestamp": data.get("timestamp"),
                "metadata": data.get("metadata", {}),
            }
        )

    return compute_basic_metrics(events)


@app.get("/stores/{store_id}/funnel")
def funnel(store_id: str):
    return get_funnel(store_id)


@app.get("/stores/{store_id}/heatmap")
def heatmap(store_id: str):
    return get_heatmap(store_id)


@app.get("/stores/{store_id}/anomalies")
def anomalies(store_id: str):
    return get_anomalies(store_id)