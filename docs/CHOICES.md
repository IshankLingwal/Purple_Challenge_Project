# Engineering Choices and Trade-Offs

## Why YOLO?

YOLO provides:

* real-time inference
* strong community support
* easy deployment

Trade-off:

* lower tracking quality compared to specialized MOT pipelines

Decision:

Use YOLO for detection and implement lightweight tracking separately.

---

## Why IoU-Based Tracking?

Advantages:

* simple
* fast
* easy to explain

Trade-off:

* track fragmentation
* identity switches

Decision:

Acceptable for a hackathon MVP.

Production systems should use DeepSORT or ByteTrack.

---

## Why Event-Driven Design?

Advantages:

* analytics derived from a single source of truth
* replay capability
* easy debugging

Trade-off:

* larger storage footprint

Decision:

Benefits outweigh costs.

---

## Why SQLite?

Advantages:

* zero setup
* lightweight
* portable

Trade-off:

* limited concurrency

Decision:

Ideal for evaluation environments.

Production deployment should use PostgreSQL.

---

## Why Rule-Based Anomaly Detection?

Advantages:

* deterministic
* explainable
* easy to validate

Trade-off:

* less adaptive than ML models

Decision:

Chosen to maximize reliability and interpretability.

---

## Why Stream Processing Instead of Batch Analytics?

Advantages:

* near real-time insights
* immediate anomaly detection
* better operational usefulness

Trade-off:

* increased implementation complexity

Decision:

Closer to real-world retail intelligence systems.

---

## Why Simulated Purchase Correlation?

The challenge dataset provides POS transactions separately from CCTV footage.

Direct identity matching is unavailable.

Decision:

Correlate purchase events with billing sessions using temporal proximity and queue activity.

This approximates real conversion tracking while respecting available data constraints.

---

## Known Limitations

* No facial recognition
* No cross-camera re-identification
* Lightweight tracking
* Simplified zone mapping

These limitations were intentionally accepted to prioritize end-to-end system completeness and business metric accuracy.

---

## Future Improvements

* DeepSORT tracking
* Kafka streaming
* PostgreSQL storage
* Real-time dashboards
* Predictive anomaly detection
* Cross-camera identity matching
* Dynamic zone configuration
