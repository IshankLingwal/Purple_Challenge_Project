from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import cv2

from pipeline.yolo_detector import PersonDetector


@dataclass
class Event:
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: str
    zone_id: str | None
    dwell_ms: int
    is_staff: bool
    confidence: float
    metadata: dict


@dataclass
class Track:
    track_id: int
    bbox: list[float]
    first_seen_ts: datetime
    last_seen_ts: datetime
    last_dwell_emit_ts: datetime | None = None
    missed_frames: int = 0
    session_seq: int = 0
    last_confidence: float = 0.5
    hits: int = 1
    confirmed: bool = False
    billing_join_emitted: bool = False


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def emit_event(events_out, event: Event) -> None:
    events_out.write(json.dumps(asdict(event)) + "\n")
    events_out.flush()


def bbox_iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    denom = area_a + area_b - inter_area
    if denom <= 0:
        return 0.0
    return inter_area / denom


def match_detections_to_tracks(
    tracks: dict[int, Track],
    detections: list[dict],
    iou_threshold: float = 0.3,
):
    track_ids = list(tracks.keys())
    det_indices = list(range(len(detections)))

    candidates = []
    for tid in track_ids:
        for di in det_indices:
            iou = bbox_iou(tracks[tid].bbox, detections[di]["bbox"])
            if iou >= iou_threshold:
                candidates.append((iou, tid, di))

    candidates.sort(reverse=True, key=lambda x: x[0])

    matched_tracks = set()
    matched_dets = set()
    assignments: dict[int, int] = {}

    for iou, tid, di in candidates:
        if tid in matched_tracks or di in matched_dets:
            continue
        matched_tracks.add(tid)
        matched_dets.add(di)
        assignments[tid] = di

    unmatched_tracks = [tid for tid in track_ids if tid not in matched_tracks]
    unmatched_dets = [di for di in det_indices if di not in matched_dets]

    return assignments, unmatched_tracks, unmatched_dets


def is_billing_camera(camera_id: str) -> bool:
    cid = camera_id.lower()
    return "bill" in cid or "billing" in cid


def process_video(
    video_path: str,
    store_id: str,
    camera_id: str,
    out_path: str,
    stride: int = 10,
    dwell_seconds: int = 30,
    max_missed_frames: int = 15,
    confirm_hits: int = 3,
    conf: float = 0.5,
):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    start_time = datetime.now(timezone.utc)

    detector = PersonDetector(conf=conf)
    tracks: dict[int, Track] = {}
    next_track_id = 1
    frame_idx = 0

    billing_queue_depth = 0
    billing_mode = is_billing_camera(camera_id)

    with open(out_path, "w", encoding="utf-8") as out:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame_idx += 1
            if frame_idx % stride != 0:
                continue

            current_ts = start_time + timedelta(seconds=frame_idx / fps)
            detections = detector.detect(frame)

            assignments, unmatched_tracks, unmatched_dets = match_detections_to_tracks(
                tracks, detections
            )

            # Update matched tracks
            for track_id, det_idx in assignments.items():
                track = tracks[track_id]
                det = detections[det_idx]

                track.bbox = det["bbox"]
                track.last_seen_ts = current_ts
                track.missed_frames = 0
                track.last_confidence = det["confidence"]
                track.hits += 1

                # Confirm a track only after repeated successful matches.
                if not track.confirmed and track.hits >= confirm_hits:
                    track.confirmed = True
                    track.session_seq = 1

                    emit_event(
                        out,
                        Event(
                            event_id=str(uuid4()),
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=f"VIS_{track_id:04d}",
                            event_type="ENTRY",
                            timestamp=iso_utc(current_ts),
                            zone_id=None,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=track.last_confidence,
                            metadata={
                                "queue_depth": None,
                                "sku_zone": None,
                                "session_seq": 1,
                            },
                        ),
                    )

                    # Billing camera: emit queue join as soon as the person is confirmed.
                    if billing_mode and not track.billing_join_emitted:
                        billing_queue_depth += 1
                        track.billing_join_emitted = True

                        emit_event(
                            out,
                            Event(
                                event_id=str(uuid4()),
                                store_id=store_id,
                                camera_id=camera_id,
                                visitor_id=f"VIS_{track_id:04d}",
                                event_type="BILLING_QUEUE_JOIN",
                                timestamp=iso_utc(current_ts),
                                zone_id="BILLING",
                                dwell_ms=0,
                                is_staff=False,
                                confidence=track.last_confidence,
                                metadata={
                                    "queue_depth": billing_queue_depth,
                                    "sku_zone": None,
                                    "session_seq": track.session_seq + 1,
                                },
                            ),
                        )

                # Emit dwell only for confirmed tracks
                if track.confirmed:
                    elapsed_seconds = (current_ts - track.first_seen_ts).total_seconds()
                    should_emit = (
                        elapsed_seconds >= dwell_seconds
                        and (
                            track.last_dwell_emit_ts is None
                            or (current_ts - track.last_dwell_emit_ts).total_seconds() >= dwell_seconds
                        )
                    )
                    if should_emit:
                        track.session_seq += 1
                        track.last_dwell_emit_ts = current_ts

                        emit_event(
                            out,
                            Event(
                                event_id=str(uuid4()),
                                store_id=store_id,
                                camera_id=camera_id,
                                visitor_id=f"VIS_{track_id:04d}",
                                event_type="ZONE_DWELL",
                                timestamp=iso_utc(current_ts),
                                zone_id="BILLING" if billing_mode else "MAIN_FLOOR",
                                dwell_ms=int(elapsed_seconds * 1000),
                                is_staff=False,
                                confidence=track.last_confidence,
                                metadata={
                                    "queue_depth": billing_queue_depth if billing_mode else None,
                                    "sku_zone": None,
                                    "session_seq": track.session_seq,
                                },
                            ),
                        )

            # Create tentative tracks for unmatched detections
            for det_idx in unmatched_dets:
                det = detections[det_idx]
                track_id = next_track_id
                next_track_id += 1

                tracks[track_id] = Track(
                    track_id=track_id,
                    bbox=det["bbox"],
                    first_seen_ts=current_ts,
                    last_seen_ts=current_ts,
                    last_dwell_emit_ts=None,
                    missed_frames=0,
                    session_seq=0,
                    last_confidence=det["confidence"],
                    hits=1,
                    confirmed=False,
                    billing_join_emitted=False,
                )

            # Age out unmatched tracks
            for track_id in unmatched_tracks:
                track = tracks[track_id]
                track.missed_frames += 1

                if track.missed_frames >= max_missed_frames:
                    # Only confirmed tracks get EXIT events.
                    if track.confirmed:
                        elapsed_seconds = (current_ts - track.first_seen_ts).total_seconds()

                        emit_event(
                            out,
                            Event(
                                event_id=str(uuid4()),
                                store_id=store_id,
                                camera_id=camera_id,
                                visitor_id=f"VIS_{track_id:04d}",
                                event_type="EXIT",
                                timestamp=iso_utc(current_ts),
                                zone_id=None,
                                dwell_ms=int(elapsed_seconds * 1000),
                                is_staff=False,
                                confidence=track.last_confidence,
                                metadata={
                                    "queue_depth": billing_queue_depth if billing_mode else None,
                                    "sku_zone": None,
                                    "session_seq": track.session_seq + 1,
                                },
                            ),
                        )

                        # Billing queue depth decreases when a confirmed visitor leaves billing.
                        if billing_mode and track.billing_join_emitted:
                            billing_queue_depth = max(0, billing_queue_depth - 1)

                    del tracks[track_id]

        # Final flush must stay inside the with-block
        final_ts = start_time + timedelta(seconds=frame_idx / fps)
        for track_id, track in list(tracks.items()):
            if not track.confirmed:
                continue

            elapsed_seconds = (final_ts - track.first_seen_ts).total_seconds()

            emit_event(
                out,
                Event(
                    event_id=str(uuid4()),
                    store_id=store_id,
                    camera_id=camera_id,
                    visitor_id=f"VIS_{track_id:04d}",
                    event_type="EXIT",
                    timestamp=iso_utc(final_ts),
                    zone_id=None,
                    dwell_ms=int(elapsed_seconds * 1000),
                    is_staff=False,
                    confidence=track.last_confidence,
                    metadata={
                        "queue_depth": billing_queue_depth if billing_mode else None,
                        "sku_zone": None,
                        "session_seq": track.session_seq + 1,
                    },
                ),
            )

            if billing_mode and track.billing_join_emitted:
                billing_queue_depth = max(0, billing_queue_depth - 1)

    cap.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--store-id", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--out", default="events.jsonl")
    parser.add_argument("--stride", type=int, default=10)
    parser.add_argument("--dwell-seconds", type=int, default=30)
    parser.add_argument("--max-missed-frames", type=int, default=15)
    parser.add_argument("--confirm-hits", type=int, default=3)
    parser.add_argument("--conf", type=float, default=0.5)
    args = parser.parse_args()

    process_video(
        args.video,
        args.store_id,
        args.camera_id,
        args.out,
        stride=args.stride,
        dwell_seconds=args.dwell_seconds,
        max_missed_frames=args.max_missed_frames,
        confirm_hits=args.confirm_hits,
        conf=args.conf,
    )
    print(f"Events written to {args.out}")


if __name__ == "__main__":
    main()