from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.pos import build_purchase_events, load_aggregated_orders, load_billing_sessions


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    with urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to the POS CSV file",
    )
    parser.add_argument(
        "--db",
        default="store_intelligence.db",
        help="Path to the local SQLite DB created by the API",
    )
    parser.add_argument(
        "--store-id",
        default="STORE_BLR_002",
        help="Challenge store id to attach the purchase events to",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/events/ingest",
        help="Ingest endpoint",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    db_path = Path(args.db)

    orders = load_aggregated_orders(csv_path)
    billing_sessions = load_billing_sessions(db_path, args.store_id)
    purchase_events = build_purchase_events(orders, billing_sessions, args.store_id)

    if not purchase_events:
        raise SystemExit("No purchase events could be generated.")

    response = post_json(args.url, {"events": purchase_events})

    print(f"Generated {len(purchase_events)} PURCHASE events")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()