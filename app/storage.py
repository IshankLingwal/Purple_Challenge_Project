import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, Table, Column, String, Float, Integer, Boolean, Text, MetaData
from sqlalchemy.orm import sessionmaker

DB_PATH = Path("./store_intelligence.db")
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
metadata = MetaData()

events_table = Table(
    "events",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("store_id", String, index=True, nullable=False),
    Column("camera_id", String, nullable=False),
    Column("visitor_id", String, index=True, nullable=False),
    Column("event_type", String, index=True, nullable=False),
    Column("timestamp", String, index=True, nullable=False),
    Column("zone_id", String, nullable=True),
    Column("dwell_ms", Integer, default=0),
    Column("is_staff", Boolean, default=False),
    Column("confidence", Float, nullable=False),
    Column("metadata_json", Text, nullable=False),
)


def init_db() -> None:
    metadata.create_all(engine)