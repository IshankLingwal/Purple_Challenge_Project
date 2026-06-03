# Store Intelligence System - Design Document

## Overview

This project implements an AI-powered Store Intelligence System that converts raw CCTV footage and POS transactions into actionable retail analytics.

The system processes customer movement inside the store, generates structured events, stores them in a database, computes business metrics, detects anomalies, and exposes analytics through REST APIs.

---

## High-Level Architecture

```text
CCTV Video
    │
    ▼
YOLO Person Detection
    │
    ▼
Multi-Object Tracking
    │
    ▼
Event Generation
(ENTRY, EXIT, ZONE_DWELL,
 BILLING_QUEUE_JOIN)
    │
    ▼
Event Ingestion API
    │
    ▼
SQLite Event Store
    │
    ├────────► Metrics API
    │
    ├────────► Funnel API
    │
    ├────────► Heatmap API
    │
    └────────► Anomaly API

POS CSV
    │
    ▼
Purchase Event Generator
    │
    ▼
Event Ingestion API
```

---

## Detection Pipeline

The detection layer uses YOLO-based person detection.

Each frame is processed periodically using a configurable stride.

Detected persons are associated with existing tracks using IoU matching.

Tracks are confirmed only after multiple successful detections to reduce false positives.

Generated events include:

* ENTRY
* EXIT
* ZONE_DWELL
* BILLING_QUEUE_JOIN
* PURCHASE

---

## Event-Driven Architecture

All analytics are derived from immutable events.

Each event contains:

* event_id
* store_id
* camera_id
* visitor_id
* timestamp
* event_type
* metadata

This design enables:

* replayability
* auditability
* easier analytics computation

---

## Storage Layer

SQLite is used as the event store.

Reasons:

* lightweight
* easy local execution
* sufficient for hackathon-scale workloads
* minimal operational complexity

In production this can be replaced by PostgreSQL.

---

## Metrics Engine

The metrics engine computes:

* unique visitors
* entries
* exits
* purchase count
* conversion rate
* abandonment rate
* average dwell by zone
* billing queue depth

---

## Funnel Engine

The funnel stages are:

ENTRY
→ ZONE_VISIT
→ BILLING_QUEUE
→ PURCHASE

Drop-off rates are calculated between stages.

---

## Heatmap Engine

Heatmap analytics aggregate:

* zone visit frequency
* average dwell time

Supported zones:

* MAIN_FLOOR
* SKINCARE
* MAKEUP
* BILLING

---

## Anomaly Detection

Current anomaly rules:

* BILLING_QUEUE_SPIKE
* CONVERSION_DROP
* DEAD_ZONE
* STALE_FEED

Rule-based detection was chosen for transparency and explainability.

---

## Testing Strategy

Automated tests cover:

* API health
* event ingestion
* metrics computation
* funnel computation
* anomaly detection
* heatmap generation

All tests pass successfully.

---

## Scalability Considerations

For production deployment:

* PostgreSQL replaces SQLite
* Kafka replaces direct ingestion
* Redis for caching
* DeepSORT/ByteTrack for tracking
* Kubernetes deployment

The current design keeps interfaces modular to support these upgrades with minimal code changes.
