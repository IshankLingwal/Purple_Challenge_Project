from collections import defaultdict


def _get(event, key, default=None):
    if isinstance(event, dict):
        return event.get(key, default)
    return getattr(event, key, default)


def compute_basic_metrics(events):
    non_staff = [e for e in events if not _get(e, "is_staff", False)]

    unique_visitors = len(
        {
            _get(e, "visitor_id")
            for e in non_staff
            if _get(e, "visitor_id") is not None
        }
    )

    entry_count = sum(1 for e in non_staff if _get(e, "event_type") == "ENTRY")
    exit_count = sum(1 for e in non_staff if _get(e, "event_type") == "EXIT")
    billing_queue_count = sum(1 for e in non_staff if _get(e, "event_type") == "BILLING_QUEUE_JOIN")
    purchase_count = sum(1 for e in non_staff if _get(e, "event_type") == "PURCHASE")

    zone_dwells = defaultdict(list)
    latest_queue_depth = 0

    for e in non_staff:
        if _get(e, "event_type") == "ZONE_DWELL" and _get(e, "zone_id"):
            zone_dwells[_get(e, "zone_id")].append(_get(e, "dwell_ms", 0))

        if _get(e, "event_type") == "BILLING_QUEUE_JOIN":
            md = _get(e, "metadata", {}) or {}
            qd = md.get("queue_depth")
            if isinstance(qd, (int, float)):
                latest_queue_depth = max(latest_queue_depth, int(qd))

    avg_dwell_by_zone = {
        zone: round(sum(values) / len(values), 2) if values else 0
        for zone, values in zone_dwells.items()
    }

    conversion_rate = round(purchase_count / unique_visitors, 4) if unique_visitors else 0.0
    abandonment_rate = (
        round(max(0, billing_queue_count - purchase_count) / billing_queue_count, 4)
        if billing_queue_count
        else 0.0
    )

    return {
        "unique_visitors": unique_visitors,
        "entry_count": entry_count,
        "exit_count": exit_count,
        "purchase_count": purchase_count,
        "billing_queue_count": billing_queue_count,
        "conversion_rate": conversion_rate,
        "abandonment_rate": abandonment_rate,
        "current_queue_depth": latest_queue_depth,
        "avg_dwell_by_zone": avg_dwell_by_zone,
    }