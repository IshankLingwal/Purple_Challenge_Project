from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class AggregatedOrder:
    order_id: str
    invoice_number: str
    source_store_id: str
    customer_number: str
    original_timestamp_utc: datetime
    basket_value_inr: float
    qty: int
    product_names: tuple[str, ...]
    brand_names: tuple[str, ...]
    dep_names: tuple[str, ...]


@dataclass(frozen=True)
class BillingSession:
    visitor_id: str
    billing_timestamp_utc: datetime
    exit_timestamp_utc: datetime | None
    queue_depth: int


def parse_iso_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_pos_timestamp(order_date: str, order_time: str) -> datetime:
    dt = datetime.strptime(f"{order_date} {order_time}", "%d-%m-%Y %H:%M:%S")
    return dt.replace(tzinfo=IST).astimezone(timezone.utc)


def load_aggregated_orders(csv_path: str | Path) -> list[AggregatedOrder]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"POS CSV not found: {csv_path}")

    groups: dict[str, list[dict[str, Any]]] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order_id = str(row["order_id"]).strip()
            groups.setdefault(order_id, []).append(row)

    orders: list[AggregatedOrder] = []

    for order_id, rows in groups.items():
        rows_sorted = sorted(rows, key=lambda r: parse_pos_timestamp(r["order_date"], r["order_time"]))
        first = rows_sorted[0]

        qty = sum(int(float(r["qty"] or 0)) for r in rows_sorted)
        basket_value = max(float(r["total_amount"] or 0) for r in rows_sorted)

        orders.append(
            AggregatedOrder(
                order_id=order_id,
                invoice_number=str(first.get("invoice_number", order_id)),
                source_store_id=str(first.get("store_id", "")).strip(),
                customer_number=str(first.get("customer_number", "")).strip(),
                original_timestamp_utc=parse_pos_timestamp(first["order_date"], first["order_time"]),
                basket_value_inr=round(basket_value, 2),
                qty=qty,
                product_names=tuple(sorted({str(r.get("product_name", "")).strip() for r in rows_sorted if r.get("product_name")})),
                brand_names=tuple(sorted({str(r.get("brand_name", "")).strip() for r in rows_sorted if r.get("brand_name")})),
                dep_names=tuple(sorted({str(r.get("dep_name", "")).strip() for r in rows_sorted if r.get("dep_name")})),
            )
        )

    orders.sort(key=lambda o: o.original_timestamp_utc)
    return orders


def load_billing_sessions(db_path: str | Path, store_id: str) -> list[BillingSession]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT visitor_id, timestamp, metadata_json
            FROM events
            WHERE store_id = ? AND event_type = 'BILLING_QUEUE_JOIN'
            ORDER BY timestamp ASC
            """,
            (store_id,),
        ).fetchall()

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            md = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            grouped.setdefault(row["visitor_id"], []).append(
                {
                    "visitor_id": row["visitor_id"],
                    "timestamp": parse_iso_ts(row["timestamp"]),
                    "metadata": md,
                }
            )

        sessions: list[BillingSession] = []
        for visitor_id, entries in grouped.items():
            for idx, entry in enumerate(entries):
                exit_ts = None
                sessions.append(
                    BillingSession(
                        visitor_id=visitor_id,
                        billing_timestamp_utc=entry["timestamp"],
                        exit_timestamp_utc=exit_ts,
                        queue_depth=int(entry["metadata"].get("queue_depth") or 0),
                    )
                )

        sessions.sort(key=lambda s: s.billing_timestamp_utc)
        return sessions
    finally:
        conn.close()


def build_purchase_events(
    orders: list[AggregatedOrder],
    billing_sessions: list[BillingSession],
    target_store_id: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if not orders:
        return events

    if billing_sessions:
        paired_orders = orders[: len(billing_sessions)]
        for order, session in zip(paired_orders, billing_sessions):
            purchase_ts = session.billing_timestamp_utc + timedelta(seconds=2)
            if session.exit_timestamp_utc is not None and purchase_ts >= session.exit_timestamp_utc:
                purchase_ts = session.exit_timestamp_utc - timedelta(seconds=1)

            event_id = str(uuid5(NAMESPACE_URL, f"{target_store_id}:{order.order_id}:{session.visitor_id}:PURCHASE"))

            events.append(
                {
                    "event_id": event_id,
                    "store_id": target_store_id,
                    "camera_id": "POS",
                    "visitor_id": session.visitor_id,
                    "event_type": "PURCHASE",
                    "timestamp": purchase_ts.isoformat().replace("+00:00", "Z"),
                    "zone_id": "BILLING",
                    "dwell_ms": 0,
                    "is_staff": False,
                    "confidence": 1.0,
                    "metadata": {
                        "queue_depth": session.queue_depth,
                        "sku_zone": None,
                        "session_seq": 3,
                        "order_id": order.order_id,
                        "invoice_number": order.invoice_number,
                        "source_store_id": order.source_store_id,
                        "customer_number": order.customer_number,
                        "original_pos_timestamp_utc": order.original_timestamp_utc.isoformat().replace("+00:00", "Z"),
                        "basket_value_inr": order.basket_value_inr,
                        "qty": order.qty,
                        "brand_names": list(order.brand_names),
                        "dep_names": list(order.dep_names),
                    },
                }
            )
    else:
        for order in orders:
            event_id = str(uuid5(NAMESPACE_URL, f"{target_store_id}:{order.order_id}:PURCHASE"))
            events.append(
                {
                    "event_id": event_id,
                    "store_id": target_store_id,
                    "camera_id": "POS",
                    "visitor_id": f"POS_{order.order_id}",
                    "event_type": "PURCHASE",
                    "timestamp": order.original_timestamp_utc.isoformat().replace("+00:00", "Z"),
                    "zone_id": "BILLING",
                    "dwell_ms": 0,
                    "is_staff": False,
                    "confidence": 1.0,
                    "metadata": {
                        "queue_depth": None,
                        "sku_zone": None,
                        "session_seq": 3,
                        "order_id": order.order_id,
                        "invoice_number": order.invoice_number,
                        "source_store_id": order.source_store_id,
                        "customer_number": order.customer_number,
                        "original_pos_timestamp_utc": order.original_timestamp_utc.isoformat().replace("+00:00", "Z"),
                        "basket_value_inr": order.basket_value_inr,
                        "qty": order.qty,
                        "brand_names": list(order.brand_names),
                        "dep_names": list(order.dep_names),
                    },
                }
            )

    return events